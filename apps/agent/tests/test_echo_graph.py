"""Exercise the real agent/tool loop without Gemini requests."""

from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from graph_fixtures import build_test_resources
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from stocker_agent.config.llm import ModelSettings, ModelTier
from stocker_agent.graphs.echo import build_echo_graph
from stocker_agent.llm import ModelRouter
from stocker_agent.skills.registry import LoadedSkill, SkillManifest, SkillMetadata


class ToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def sample_skill(required_tools=("print_user_message",), allowed_agents=("echo",)):
    return LoadedSkill(
        SkillMetadata(name="echo-agent", description="Echo test"),
        SkillManifest(
            id="echo-agent",
            version="1",
            llm_model="instant",
            required_tools=required_tools,
            allowed_agents=allowed_agents,
        ),
        "Print the greeting, then echo it.",
        "test-hash",
    )


@pytest.mark.asyncio
async def test_echo_executes_tool_and_preserves_messages(capsys):
    model = ToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "print_user_message",
                        "args": {"message": "hello"},
                        "id": "greeting-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Echo: hello"),
        ]
    )
    registry = Mock()
    registry.get.return_value = sample_skill()
    models = Mock()
    models.get.return_value = model
    result = await build_echo_graph(
        build_test_resources(skills=registry, models=models)
    ).ainvoke({"messages": [HumanMessage(content="hello")]})
    assert capsys.readouterr().out == "hello\n"
    assert len(result["messages"]) == 4
    assert isinstance(result["messages"][2], ToolMessage)
    assert result["messages"][-1].content == "Echo: hello"
    models.get.assert_called_once_with(ModelTier.INSTANT)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "skill",
    [
        sample_skill(required_tools=("unapproved_tool",)),
        sample_skill(allowed_agents=("other",)),
    ],
)
async def test_echo_rejects_manifest_outside_policy(skill):
    registry = Mock()
    registry.get.return_value = skill
    models = Mock()
    with pytest.raises(ValueError):
        await build_echo_graph(
            build_test_resources(skills=registry, models=models)
        ).ainvoke({"messages": [HumanMessage(content="hello")]})
    models.get.assert_not_called()


@pytest.mark.asyncio
async def test_complex_tier_routes_through_openrouter_and_calls_tools(capsys):
    model = ToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "print_user_message",
                        "args": {"message": "hello"},
                        "id": "router-tool",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Echo: hello"),
        ]
    )
    skill = sample_skill()
    skill = replace(
        skill,
        manifest=skill.manifest.model_copy(update={"llm_model": ModelTier.COMPLEX}),
    )
    registry = Mock(get=Mock(return_value=skill))
    settings = ModelSettings(
        complex={"provider": "openrouter", "model": "test-opus"},
        openrouter_api_key="fake-router-key",
    )
    with patch(
        "stocker_agent.llm.openrouter.ChatOpenRouter", return_value=model
    ) as create:
        result = await build_echo_graph(
            build_test_resources(skills=registry, models=ModelRouter(settings))
        ).ainvoke({"messages": [HumanMessage(content="hello")]})
    assert capsys.readouterr().out == "hello\n"
    assert isinstance(result["messages"][2], ToolMessage)
    assert result["messages"][-1].content == "Echo: hello"
    assert create.call_args.kwargs["model"] == "test-opus"

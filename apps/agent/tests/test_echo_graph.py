"""Exercise the real agent/tool loop without Gemini requests."""

from unittest.mock import Mock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from stocker_agent.config.llm import ModelTier
from stocker_agent.graphs.echo import build_echo_graph
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
    result = await build_echo_graph(registry, models).ainvoke(
        {"messages": [HumanMessage(content="hello")]}
    )
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
        await build_echo_graph(registry, models).ainvoke(
            {"messages": [HumanMessage(content="hello")]}
        )
    models.get.assert_not_called()

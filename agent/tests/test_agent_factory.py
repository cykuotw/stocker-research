"""Agent policy boundaries and invocation configuration without model requests."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from stocker_agent.agent_runtime import factory as module
from stocker_agent.agent_runtime.definitions import ECHO_AGENT, AgentDefinition
from stocker_agent.agent_runtime.factory import AgentFactory
from stocker_agent.skills.registry import LoadedSkill, SkillManifest, SkillMetadata
from stocker_agent.tools.greeting import print_user_message
from stocker_agent.tools.registry import ToolRegistry


def skill(**overrides):
    return LoadedSkill(
        SkillMetadata(name="echo-agent", description="test"),
        SkillManifest.model_validate(
            {
                "id": "echo-agent",
                "version": "1",
                "llm_model": "instant",
                "required_tools": ["print_user_message"],
                "allowed_agents": ["echo"],
                **overrides,
            }
        ),
        "Echo instructions",
        "test-hash",
    )


@pytest.mark.parametrize(
    "overrides,registered",
    [
        ({"required_tools": ["disallowed"]}, True),
        ({"allowed_agents": ["other"]}, True),
        ({"status": "inactive"}, True),
        ({}, False),
    ],
)
def test_policy_failures_precede_model_creation(overrides, registered, monkeypatch):
    models = Mock()
    constructor = Mock()
    monkeypatch.setattr(module, "create_agent", constructor)
    factory = AgentFactory(
        models,
        Mock(get=Mock(return_value=skill(**overrides))),
        ToolRegistry([print_user_message] if registered else []),
    )
    with pytest.raises(ValueError):
        factory.build(ECHO_AGENT)
    models.get.assert_not_called()
    constructor.assert_not_called()


def test_tool_resolution_deduplicates_and_does_not_expose_extra_tools(monkeypatch):
    from langchain_core.tools import tool

    @tool
    def extra() -> str:
        """An available tool not required by this skill."""
        return "extra"

    constructor = Mock()
    monkeypatch.setattr(module, "create_agent", constructor)
    definition = AgentDefinition(
        id="echo",
        skill_id="echo-agent",
        allowed_tools={"print_user_message", "extra"},
    )
    factory = AgentFactory(
        Mock(),
        Mock(get=Mock(return_value=skill(required_tools=["print_user_message"] * 2))),
        ToolRegistry([print_user_message, extra]),
    )
    factory.build(definition)
    assert constructor.call_args.kwargs["tools"] == [print_user_message]
    assert constructor.call_args.kwargs["system_prompt"] == "Echo instructions"
    assert "checkpointer" not in constructor.call_args.kwargs


@pytest.mark.asyncio
async def test_agent_preserves_request_config_without_mutation(monkeypatch):
    graph = Mock(
        ainvoke=AsyncMock(return_value={"messages": [AIMessage(content="ok")]})
    )
    monkeypatch.setattr(module, "create_agent", Mock(return_value=graph))
    factory = AgentFactory(
        Mock(),
        Mock(get=Mock(return_value=skill(allowed_agents=[]))),
        ToolRegistry([print_user_message]),
    )
    config = {
        "configurable": {"thread_id": "test-thread"},
        "tags": ["request"],
        "recursion_limit": 100,
        "metadata": {"runtime_run_id": "test-run", "skill_id": "untrusted"},
    }
    # The same trusted definition can be composed by distinct workflows.
    for _ in range(2):
        agent = factory.build(ECHO_AGENT)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="hello")]}, config
        )
        assert result["messages"][-1].content == "ok"
    actual = graph.ainvoke.call_args.args[1]
    assert actual["configurable"] == config["configurable"]
    assert actual["tags"] == ["request"]
    assert actual["recursion_limit"] == ECHO_AGENT.recursion_limit
    assert actual["metadata"] == {
        "runtime_run_id": "test-run",
        "agent_id": "echo",
        "skill_id": "echo-agent",
        "skill_version": "1",
        "skill_hash": "test-hash",
        "llm_tier": "instant",
    }
    assert config["metadata"]["skill_id"] == "untrusted"
    assert config["recursion_limit"] == 100


def test_agent_definition_is_immutable_and_limits_are_validated():
    with pytest.raises(ValidationError):
        ECHO_AGENT.recursion_limit = 20
    with pytest.raises(ValidationError):
        AgentDefinition(id="echo", skill_id="echo-agent", recursion_limit=0)

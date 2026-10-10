"""A skill-driven AI node for checking model and tool integration."""

from langchain.agents import create_agent
from langchain.agents.middleware.types import InputAgentState
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from stocker_agent.llm import ModelProvider
from stocker_agent.skills.registry import SkillRegistry
from stocker_agent.tools.greeting import print_user_message


def build_echo_graph(
    registry: SkillRegistry | None = None,
    models: ModelProvider | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Name the node from skill metadata; defer model creation until first use."""
    skill_registry = registry if registry is not None else SkillRegistry.from_settings()
    node_name = skill_registry.get("echo-agent").metadata.name
    model_provider = models

    async def echo_agent(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, list[BaseMessage]]:
        nonlocal model_provider
        if model_provider is None:
            model_provider = ModelProvider()
        skill = skill_registry.get("echo-agent")
        if (
            skill.manifest.allowed_agents
            and "echo" not in skill.manifest.allowed_agents
        ):
            raise ValueError("echo-agent is not allowed for the echo agent")
        # This agent permits only this console tool. Skills cannot expand policy.
        available = {print_user_message.name: print_user_message}
        requested = skill.manifest.required_tools
        unsupported = set(requested) - available.keys()
        if unsupported:
            raise ValueError(f"Unsupported echo tools: {sorted(unsupported)}")
        agent = create_agent(
            model=model_provider.get(skill.manifest.llm_model),
            tools=[available[name] for name in dict.fromkeys(requested)],
            system_prompt=skill.instructions,
        )
        messages = state["messages"]
        agent_input: InputAgentState = {"messages": list(messages)}
        result = await agent.ainvoke(
            agent_input,
            config={
                **config,
                "recursion_limit": 10,
                "metadata": {
                    **config.get("metadata", {}),
                    "skill_id": skill.manifest.id,
                    "skill_version": skill.manifest.version,
                    "skill_hash": skill.content_hash,
                    "llm_tier": skill.manifest.llm_model.value,
                },
            },
        )
        return {"messages": result["messages"][len(messages) :]}

    return (
        # LangGraph supports MessagesState; ty misidentifies its StateLike bound.
        StateGraph(MessagesState)  # ty: ignore[invalid-argument-type]
        .add_node(node_name, echo_agent)
        .add_edge(START, node_name)
        .add_edge(node_name, END)
        .compile(checkpointer=checkpointer)
    )


graph = build_echo_graph()

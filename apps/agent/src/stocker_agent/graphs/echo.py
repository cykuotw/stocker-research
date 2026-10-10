"""A skill-driven AI node for checking model and tool integration."""

from langchain.agents import create_agent
from langchain.agents.middleware.types import InputAgentState
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from stocker_agent.graph_runtime.resources import GraphResources


def build_echo_graph(resources: GraphResources) -> CompiledStateGraph:
    """Build one graph with application-scoped resources; clients remain lazy."""
    skill_registry = resources.skills
    node_name = skill_registry.get("echo-agent").metadata.name

    async def echo_agent(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, list[BaseMessage]]:
        skill = skill_registry.get("echo-agent")
        if (
            skill.manifest.allowed_agents
            and "echo" not in skill.manifest.allowed_agents
        ):
            raise ValueError("echo-agent is not allowed for the echo agent")
        # This agent permits only this console tool. Skills cannot expand policy.
        allowed_tools = {"print_user_message"}
        requested = skill.manifest.required_tools
        unsupported = set(requested) - allowed_tools
        if unsupported:
            raise ValueError(f"Unsupported echo tools: {sorted(unsupported)}")
        agent = create_agent(
            model=resources.models.get(skill.manifest.llm_model),
            tools=[resources.tools.get(name) for name in dict.fromkeys(requested)],
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
        .compile(checkpointer=resources.checkpointer)
    )

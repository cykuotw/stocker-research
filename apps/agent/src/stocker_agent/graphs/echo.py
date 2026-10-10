"""A skill-driven AI node for checking model and tool integration."""

from langchain.agents.middleware.types import InputAgentState
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from stocker_agent.agent_runtime.definitions import ECHO_AGENT
from stocker_agent.agent_runtime.factory import AgentFactory
from stocker_agent.graph_runtime.resources import GraphResources


def build_echo_graph(resources: GraphResources) -> CompiledStateGraph:
    """Build one graph with application-scoped resources; clients remain lazy."""
    factory = AgentFactory(resources.models, resources.skills, resources.tools)
    node_name = resources.skills.get(ECHO_AGENT.skill_id).metadata.name

    async def echo_agent(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, list[BaseMessage]]:
        agent = factory.build(ECHO_AGENT)
        messages = state["messages"]
        agent_input: InputAgentState = {"messages": list(messages)}
        result = await agent.ainvoke(agent_input, config)
        new_messages: list[BaseMessage] = list(result["messages"][len(messages) :])
        return {"messages": new_messages}

    return (
        # LangGraph supports MessagesState; ty misidentifies its StateLike bound.
        StateGraph(MessagesState)  # ty: ignore[invalid-argument-type]
        .add_node(node_name, echo_agent)
        .add_edge(START, node_name)
        .add_edge(node_name, END)
        .compile(checkpointer=resources.checkpointer)
    )

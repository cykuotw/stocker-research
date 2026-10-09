"""A model-free chat graph for checking the local server and UI."""

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph


def echo(state: MessagesState) -> dict[str, list[AIMessage]]:
    messages = state["messages"]
    text = messages[-1].text if messages else "Hello!"
    return {"messages": [AIMessage(content=f"Echo: {text}")]}


graph = (
    StateGraph(MessagesState)
    .add_node("echo", echo)
    .add_edge(START, "echo")
    .add_edge("echo", END)
    .compile()
)

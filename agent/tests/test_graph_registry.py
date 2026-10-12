"""Explicit registration and shared-resource compilation without external I/O."""

from unittest.mock import Mock

import pytest
from graph_fixtures import build_test_resources
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from stocker_agent.graph_runtime.catalog import GRAPH_FACTORIES
from stocker_agent.graph_runtime.registry import GraphRegistry
from stocker_agent.tools.greeting import print_user_message
from stocker_agent.tools.registry import ToolRegistry


def test_factories_share_resources_and_checkpointer():
    saver = InMemorySaver()
    resources = build_test_resources(saver)
    received = []

    def build(shared):
        received.append(shared)
        return (
            StateGraph(MessagesState)
            .add_node("noop", lambda state: {})
            .add_edge(START, "noop")
            .add_edge("noop", END)
            .compile(checkpointer=shared.checkpointer)
        )

    graphs = GraphRegistry({"first": build, "second": build}).build(resources)
    assert set(graphs) == {"first", "second"}
    assert all(item is resources for item in received)
    assert all(graph.checkpointer is saver for graph in graphs.values())
    assert graphs["first"] is not graphs["second"]


def test_duplicate_and_invalid_registration_fail():
    factory = Mock()
    registry = GraphRegistry({"echo": factory})
    with pytest.raises(ValueError, match="already registered"):
        registry.register("echo", factory)
    with pytest.raises(ValueError, match="Graph ID"):
        registry.register(" ", factory)
    with pytest.raises(TypeError, match="not callable"):
        registry.register("broken", None)


def test_invalid_factory_result_fails_startup():
    with pytest.raises(TypeError, match="CompiledStateGraph: broken"):
        GraphRegistry({"broken": lambda resources: object()}).build(
            build_test_resources()
        )


def test_empty_registry_does_not_fall_back_to_echo():
    assert GraphRegistry({}).build(build_test_resources()) == {}


def test_catalog_import_does_not_create_graph_instances():
    from stocker_agent.graphs import echo

    assert GRAPH_FACTORIES == {"echo": echo.build_echo_graph}
    assert not hasattr(echo, "graph")


def test_tool_registration_and_missing_tool():
    tools = ToolRegistry([print_user_message])
    assert tools.get("print_user_message") is print_user_message
    with pytest.raises(ValueError, match="already registered"):
        tools.register(print_user_message)
    with pytest.raises(ValueError, match="not registered"):
        tools.get("unknown")

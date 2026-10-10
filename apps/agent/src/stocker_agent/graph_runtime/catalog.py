"""Built-in workflow IDs and factories; importing does not compile graphs."""

from stocker_agent.graph_runtime.registry import GraphFactory
from stocker_agent.graphs.echo import build_echo_graph

GRAPH_FACTORIES: dict[str, GraphFactory] = {
    "echo": build_echo_graph,
}

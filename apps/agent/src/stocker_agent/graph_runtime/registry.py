"""Explicit graph factory registration and startup compilation."""

from collections.abc import Callable, Mapping

from langgraph.graph.state import CompiledStateGraph

from stocker_agent.graph_runtime.resources import GraphResources

GraphFactory = Callable[[GraphResources], CompiledStateGraph]


class GraphRegistry:
    def __init__(self, factories: Mapping[str, GraphFactory]) -> None:
        self._factories: dict[str, GraphFactory] = {}
        for graph_id, factory in factories.items():
            self.register(graph_id, factory)

    def register(self, graph_id: str, factory: GraphFactory) -> None:
        if not graph_id.strip() or len(graph_id) > 100:
            raise ValueError("Graph ID must contain 1 to 100 characters")
        if graph_id in self._factories:
            raise ValueError(f"Graph already registered: {graph_id}")
        if not callable(factory):
            raise TypeError(f"Graph factory is not callable: {graph_id}")
        self._factories[graph_id] = factory

    def build(self, resources: GraphResources) -> dict[str, CompiledStateGraph]:
        graphs = {}
        for graph_id, factory in self._factories.items():
            graph = factory(resources)
            if not isinstance(graph, CompiledStateGraph):
                raise TypeError(
                    f"Graph factory must return CompiledStateGraph: {graph_id}"
                )
            graphs[graph_id] = graph
        return graphs

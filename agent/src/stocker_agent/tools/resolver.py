"""Resolve required tools without granting permissions from a skill manifest."""

from collections.abc import Sequence
from collections.abc import Set as AbstractSet

from langchain_core.tools import BaseTool

from stocker_agent.tools.registry import ToolRegistry


def resolve_tools(
    registry: ToolRegistry,
    *,
    required_tools: Sequence[str],
    allowed_tools: AbstractSet[str],
) -> list[BaseTool]:
    denied = set(required_tools) - allowed_tools
    if denied:
        raise ValueError(f"Required tools are not allowed: {', '.join(sorted(denied))}")
    # Required means mandatory: missing registrations fail instead of being dropped.
    return [registry.get(name) for name in dict.fromkeys(required_tools)]

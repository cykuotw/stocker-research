"""Application-scoped resources shared by graph factories."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from langgraph.checkpoint.base import BaseCheckpointSaver

from stocker_agent.llm import ModelRouter
from stocker_agent.skills.registry import SkillRegistry
from stocker_agent.tools.greeting import print_user_message
from stocker_agent.tools.registry import ToolRegistry


@dataclass(frozen=True)
class GraphResources:
    checkpointer: BaseCheckpointSaver | None
    models: ModelRouter
    skills: SkillRegistry
    tools: ToolRegistry

    @classmethod
    def from_settings(cls, checkpointer: BaseCheckpointSaver) -> Self:
        return cls(
            checkpointer=checkpointer,
            models=ModelRouter(),
            skills=SkillRegistry.from_settings(),
            tools=ToolRegistry([print_user_message]),
        )


GraphResourcesFactory = Callable[[BaseCheckpointSaver], GraphResources]

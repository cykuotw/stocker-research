"""Graph resources for deterministic tests without private settings or models."""

from unittest.mock import Mock

from stocker_agent.graph_runtime.resources import GraphResources
from stocker_agent.llm import ModelRouter
from stocker_agent.skills.registry import SkillRegistry
from stocker_agent.tools.greeting import print_user_message
from stocker_agent.tools.registry import ToolRegistry


def build_test_resources(checkpointer=None, *, skills=None, models=None):
    return GraphResources(
        checkpointer=checkpointer,
        models=models if models is not None else Mock(spec=ModelRouter),
        skills=skills if skills is not None else Mock(spec=SkillRegistry),
        tools=ToolRegistry([print_user_message]),
    )

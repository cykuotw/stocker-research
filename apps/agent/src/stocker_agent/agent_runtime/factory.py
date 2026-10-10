"""Validate policies and compose skill instructions, models, and tools."""

from dataclasses import dataclass
from typing import cast

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentState, InputAgentState
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from stocker_agent.agent_runtime.definitions import AgentDefinition
from stocker_agent.llm import ModelRouter
from stocker_agent.skills.registry import LoadedSkill, SkillRegistry
from stocker_agent.tools.registry import ToolRegistry
from stocker_agent.tools.resolver import resolve_tools


@dataclass(frozen=True)
class SkillAgent:
    definition: AgentDefinition
    skill: LoadedSkill
    graph: CompiledStateGraph

    async def ainvoke(
        self, value: InputAgentState, config: RunnableConfig
    ) -> AgentState[object]:
        invocation_config: RunnableConfig = {
            **config,
            "recursion_limit": self.definition.recursion_limit,
            "metadata": {
                **config.get("metadata", {}),
                "agent_id": self.definition.id,
                "skill_id": self.skill.manifest.id,
                "skill_version": self.skill.manifest.version,
                "skill_hash": self.skill.content_hash,
                "llm_tier": self.skill.manifest.llm_model.value,
            },
        }
        # create_agent's compiled graph returns AgentState for this input schema.
        return cast(
            AgentState[object], await self.graph.ainvoke(value, invocation_config)
        )


class AgentFactory:
    def __init__(
        self, models: ModelRouter, skills: SkillRegistry, tools: ToolRegistry
    ) -> None:
        self.models = models
        self.skills = skills
        self.tools = tools

    def build(self, definition: AgentDefinition) -> SkillAgent:
        skill = self.skills.get(definition.skill_id)
        if skill.manifest.status != "active":
            raise ValueError(f"Skill is inactive: {definition.skill_id}")
        allowed = skill.manifest.allowed_agents
        if allowed and definition.id not in allowed:
            raise ValueError(
                f"Skill {definition.skill_id} is not allowed for {definition.id}"
            )
        tools = resolve_tools(
            self.tools,
            required_tools=skill.manifest.required_tools,
            allowed_tools=definition.allowed_tools,
        )
        # Validate authorization and availability before constructing model clients.
        graph = create_agent(
            model=self.models.get(skill.manifest.llm_model),
            tools=tools,
            system_prompt=skill.instructions,
        )
        return SkillAgent(definition, skill, graph)

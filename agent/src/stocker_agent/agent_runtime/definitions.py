"""Trusted application policies; skill manifests cannot expand permissions."""

from pydantic import BaseModel, ConfigDict, Field

from stocker_agent.skills.registry import SKILL_ID


class AgentDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=SKILL_ID, max_length=64)
    skill_id: str = Field(pattern=SKILL_ID, max_length=64)
    allowed_tools: frozenset[str] = frozenset()
    recursion_limit: int = Field(default=10, gt=0)


ECHO_AGENT = AgentDefinition(
    id="echo", skill_id="echo-agent", allowed_tools=frozenset({"print_user_message"})
)

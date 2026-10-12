"""Typed assistants HTTP models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stocker_agent.app.models.graphs import GraphConfig


class AssistantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    config: GraphConfig = Field(default_factory=GraphConfig)


class Assistant(AssistantInput):
    assistant_id: UUID
    created_at: datetime

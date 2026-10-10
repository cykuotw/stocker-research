"""Typed sessions HTTP models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stocker_agent.app.models.graphs import GraphConfig


class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assistant_id: UUID
    title: str = Field(default="New session", max_length=200)


class Session(SessionInput):
    session_id: UUID
    graph_id: str
    config: GraphConfig
    created_at: datetime

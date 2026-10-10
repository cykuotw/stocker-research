"""Typed graphs HTTP models."""

from pydantic import BaseModel, ConfigDict, Field


class GraphConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recursion_limit: int = Field(default=25, ge=1, le=100)

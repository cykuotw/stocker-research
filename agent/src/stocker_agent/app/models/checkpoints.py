"""Typed checkpoints HTTP models."""

from pydantic import BaseModel, JsonValue


class StateView(BaseModel):
    values: dict[str, JsonValue]
    next: list[str]
    checkpoint_id: str | None
    created_at: str | None
    metadata: JsonValue
    interrupts: list[JsonValue]


class CheckpointComparison(BaseModel):
    left: StateView
    right: StateView
    changed_keys: list[str]

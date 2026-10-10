"""Typed HTTP records and execution inputs; graph state remains checkpoint-owned."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

RunStatus = Literal[
    "pending",
    "running",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
    "recovery_required",
]
ACTIVE_STATUSES = ("pending", "running")
TERMINAL_STATUSES = (
    "interrupted",
    "completed",
    "failed",
    "cancelled",
    "recovery_required",
)


class GraphConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recursion_limit: int = Field(default=25, ge=1, le=100)


class AssistantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    config: GraphConfig = Field(default_factory=GraphConfig)


class Assistant(AssistantInput):
    assistant_id: UUID
    created_at: datetime


class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assistant_id: UUID
    title: str = Field(default="New session", max_length=200)


class Session(SessionInput):
    session_id: UUID
    graph_id: str
    config: GraphConfig
    created_at: datetime


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["input", "resume", "recover"] = "input"
    input: dict[str, JsonValue] | None = None
    resume: JsonValue = None
    idempotency_key: str = Field(min_length=1, max_length=200)
    acknowledge_replay: bool = False

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "input" and (
            self.input is None or "resume" in self.model_fields_set
        ):
            raise ValueError("input action requires input and no resume value")
        if self.action == "resume" and (
            self.input is not None or "resume" not in self.model_fields_set
        ):
            raise ValueError("resume action requires resume and no input")
        if self.action == "recover" and (
            self.input is not None
            or "resume" in self.model_fields_set
            or not self.acknowledge_replay
        ):
            raise ValueError(
                "recover requires acknowledge_replay=true and no input/resume"
            )
        return self


class Run(BaseModel):
    run_id: UUID
    session_id: UUID
    status: RunStatus
    action: Literal["input", "resume", "recover"]
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    error: dict[str, JsonValue] | None = None


class RuntimeEvent(BaseModel):
    event_id: int
    session_id: UUID
    run_id: UUID
    kind: str
    created_at: datetime
    payload: JsonValue
    durable: Literal[True] = True


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

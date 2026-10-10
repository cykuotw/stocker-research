"""Typed events HTTP models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, JsonValue


class RuntimeEvent(BaseModel):
    event_id: int
    session_id: UUID
    run_id: UUID
    kind: str
    created_at: datetime
    payload: JsonValue
    durable: Literal[True] = True

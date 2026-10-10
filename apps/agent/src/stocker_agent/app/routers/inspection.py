from collections.abc import AsyncIterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from stocker_agent.app.dependencies import RegisteredRun, Service
from stocker_agent.app.models import (
    CheckpointComparison,
    RuntimeEvent,
    StateView,
)

Limit = Annotated[int, Query(ge=1, le=200)]
After = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/api", tags=["inspection"])


@router.get("/sessions/{session_id}/state")
async def state(session_id: UUID, service: Service) -> StateView:
    return await service.state(session_id)


@router.get("/sessions/{session_id}/checkpoints")
async def checkpoints(
    session_id: UUID, service: Service, limit: Limit = 50, before: str | None = None
) -> list[StateView]:
    return await service.history(session_id, before, limit)


@router.get("/sessions/{session_id}/checkpoints/compare")
async def compare(
    session_id: UUID, left: str, right: str, service: Service
) -> CheckpointComparison:
    return await service.compare(session_id, left, right)


@router.get("/sessions/{session_id}/checkpoints/{checkpoint_id}")
async def checkpoint(
    session_id: UUID, checkpoint_id: str, service: Service
) -> StateView:
    return await service.state(session_id, checkpoint_id)


@router.get("/runs/{run_id}/events")
async def events(
    run_id: UUID, service: Service, after: After = 0, limit: Limit = 50
) -> list[RuntimeEvent]:
    return await service.events(run_id, after, limit)


@router.get("/sessions/{session_id}/events")
async def session_events(
    session_id: UUID, service: Service, after: After = 0, limit: Limit = 50
) -> list[RuntimeEvent]:
    return await service.session_events(session_id, after, limit)


@router.get(
    "/runs/{run_id}/events/stream",
    response_class=EventSourceResponse,
    response_model=None,
)
async def stream(
    run_id: UUID,
    existing: RegisteredRun,
    service: Service,
    request: Request,
    after: After = 0,
    last_event_id: Annotated[int | None, Header(ge=0)] = None,
) -> AsyncIterable[ServerSentEvent]:
    if last_event_id is not None:
        after = max(after, last_event_id)
    async for item in service.stream_events(run_id, after):
        if await request.is_disconnected():
            break
        yield ServerSentEvent(
            data=item.model_dump(mode="json"), event=item.kind, id=str(item.event_id)
        )

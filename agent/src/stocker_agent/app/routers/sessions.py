from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from stocker_agent.app.dependencies import Service
from stocker_agent.app.models import (
    Assistant,
    AssistantInput,
    Session,
    SessionInput,
)

Limit = Annotated[int, Query(ge=1, le=200)]
After = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/assistants", status_code=201)
async def create_assistant(body: AssistantInput, service: Service) -> Assistant:
    return await service.create_assistant(body)


@router.get("/assistants")
async def assistants(
    service: Service, limit: Limit = 50, after: UUID | None = None
) -> list[Assistant]:
    return await service.assistants(after, limit)


@router.get("/assistants/{assistant_id}")
async def assistant(assistant_id: UUID, service: Service) -> Assistant:
    return await service.assistant(assistant_id)


@router.post("/sessions", status_code=201)
async def create_session(body: SessionInput, service: Service) -> Session:
    return await service.create_session(body)


@router.get("/sessions")
async def sessions(
    service: Service, limit: Limit = 50, after: UUID | None = None
) -> list[Session]:
    return await service.sessions(after, limit)


@router.get("/sessions/{session_id}")
async def session(session_id: UUID, service: Service) -> Session:
    return await service.session(session_id)

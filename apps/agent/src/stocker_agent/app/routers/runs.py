from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from stocker_agent.app.dependencies import Runner, Service
from stocker_agent.app.models import (
    Run,
    RunInput,
)

Limit = Annotated[int, Query(ge=1, le=200)]
After = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/sessions/{session_id}/runs", status_code=202)
async def submit(session_id: UUID, body: RunInput, service: Service) -> Run:
    return await service.submit(session_id, body)


@router.get("/sessions/{session_id}/runs")
async def runs(
    session_id: UUID, service: Service, limit: Limit = 50, after: UUID | None = None
) -> list[Run]:
    return await service.runs(session_id, after, limit)


@router.get("/runs/{run_id}")
async def run(run_id: UUID, service: Service) -> Run:
    return await service.run(run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel(run_id: UUID, runner: Runner) -> Run:
    return Run.model_validate(await runner.cancel(run_id))

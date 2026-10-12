"""Registered run lookup dependency."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends

from stocker_agent.app.dependencies.services import Service
from stocker_agent.app.models import Run


async def registered_run(run_id: UUID, service: Service) -> Run:
    # Resolve before starting an SSE response so missing runs return JSON 404.
    return await service.run(run_id)


RegisteredRun = Annotated[Run, Depends(registered_run)]

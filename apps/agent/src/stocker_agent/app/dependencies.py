"""Typed HTTP dependencies; plain services use constructor injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from stocker_agent.app.context import AppContext
from stocker_agent.app.errors import RuntimeProblem
from stocker_agent.app.models import Run
from stocker_agent.app.runner import GraphRunner
from stocker_agent.app.service import SessionService


def get_context(request: Request) -> AppContext:
    context = getattr(request.app.state, "context", None)
    if not isinstance(context, AppContext):
        raise RuntimeProblem("runtime_unavailable", 503)
    return context


Context = Annotated[AppContext, Depends(get_context)]


async def get_service(context: Context) -> SessionService:
    return context.service


async def get_runner(context: Context) -> GraphRunner:
    return context.runner


Service = Annotated[SessionService, Depends(get_service)]
Runner = Annotated[GraphRunner, Depends(get_runner)]


async def registered_run(run_id: UUID, service: Service) -> Run:
    # Resolve before starting an SSE response so missing runs return JSON 404.
    return await service.run(run_id)


RegisteredRun = Annotated[Run, Depends(registered_run)]

from typing import Annotated

from fastapi import APIRouter, Query

from stocker_agent.app.core.errors import RuntimeProblem
from stocker_agent.app.dependencies import Runner, Service

Limit = Annotated[int, Query(ge=1, le=200)]
After = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="", tags=["system"])


@router.get("/health")
async def health(service: Service, runner: Runner) -> dict[str, str]:
    if runner.failure:
        raise RuntimeProblem("worker_unavailable", 503)
    await service.ready()
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict[str, str | bool]:
    return {
        "runtime": "custom-fastapi",
        "tracing": False,
        "protocol": "stocker-runtime-v1",
    }


@router.get("/api/graphs")
async def graphs(service: Service) -> list[str]:
    return service.graph_ids()

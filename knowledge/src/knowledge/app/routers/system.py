"""System HTTP endpoints."""

from fastapi import APIRouter, HTTPException
from psycopg import Error
from psycopg_pool import PoolTimeout

from knowledge.app.dependencies.database import Database
from knowledge.app.models.system import HealthResponse, ServiceInfo

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(database: Database) -> HealthResponse:
    """Database readiness; retrieval and document pipelines remain planned."""
    try:
        await database.ready()
    except Error, PoolTimeout:
        raise HTTPException(status_code=503, detail="database_unavailable") from None
    return HealthResponse()


@router.get("/info")
def info() -> ServiceInfo:
    return ServiceInfo()

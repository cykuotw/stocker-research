"""System HTTP endpoints."""

from fastapi import APIRouter

from knowledge.app.models.system import HealthResponse, ServiceInfo

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> HealthResponse:
    """Process liveness only; does not assert retrieval or database readiness."""
    return HealthResponse()


@router.get("/info")
def info() -> ServiceInfo:
    return ServiceInfo()

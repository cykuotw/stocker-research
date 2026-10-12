"""System endpoint responses and implemented capability metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ServiceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    service: Literal["stocker-knowledge"] = "stocker-knowledge"
    version: Literal["0.1.0"] = "0.1.0"
    implemented_capabilities: tuple[str, ...] = (
        "health",
        "service_info",
        "postgres_connection",
    )
    planned_capabilities: tuple[str, ...] = (
        "document_ingestion",
        "knowledge_extraction",
        "postgres_persistence",
        "retrieval",
        "mcp",
    )

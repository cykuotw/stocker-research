"""Verify that Knowledge startup is independent of the copied Agent runtime."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from knowledge.app.core.factory import create_app
from knowledge.app.database.factory import DatabaseFactory, DatabaseResources
from knowledge.config.app import AppSettings
from knowledge.config.database import DatabaseSettings


class FakeDatabaseFactory(DatabaseFactory):
    def __init__(self):
        self.resources = DatabaseResources(MagicMock())
        self.closed = False

    @asynccontextmanager
    async def open(
        self, settings: DatabaseSettings
    ) -> AsyncGenerator[DatabaseResources]:
        try:
            yield self.resources
        finally:
            self.closed = True


@pytest.fixture(autouse=True)
def fake_readiness(monkeypatch):
    check = AsyncMock()
    monkeypatch.setattr(DatabaseResources, "ready", check)
    return check


def test_service_starts_without_agent_database_skills_or_models(monkeypatch):
    monkeypatch.setenv("DB_NAME", "stocker_research")
    monkeypatch.setenv("SKILL_MODE", "s3")
    with (
        patch("socket.socket.connect", side_effect=AssertionError("network access")),
        TestClient(create_app(database_factory=FakeDatabaseFactory())) as client,
    ):
        assert client.get("/health").json() == {"status": "ok"}
        info = client.get("/info").json()
        assert info["service"] == "stocker-knowledge"
        assert info["implemented_capabilities"] == [
            "health",
            "service_info",
            "postgres_connection",
        ]
        assert "retrieval" in info["planned_capabilities"]
        assert "mcp" in info["planned_capabilities"]
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "Stocker Knowledge Service"
        assert set(schema["paths"]) == {"/health", "/info"}


@pytest.mark.parametrize(
    "path", ["/api/graphs", "/api/assistants", "/api/sessions", "/mcp"]
)
def test_copied_runtime_and_unimplemented_mcp_are_not_exposed(path):
    with TestClient(create_app(database_factory=FakeDatabaseFactory())) as client:
        assert client.get(path).status_code == 404


def test_configured_cors_allows_only_selected_origins():
    app = create_app(
        AppSettings(cors_origins=["https://consumer.example"]),
        database_factory=FakeDatabaseFactory(),
    )
    with TestClient(app) as client:
        allowed = client.get("/info", headers={"Origin": "https://consumer.example"})
        denied = client.get("/info", headers={"Origin": "https://other.example"})
        assert (
            allowed.headers["access-control-allow-origin"] == "https://consumer.example"
        )
        assert "access-control-allow-origin" not in denied.headers


def test_lifespan_exposes_and_clears_database():
    factory = FakeDatabaseFactory()
    app = create_app(database_factory=factory)
    with TestClient(app) as client:
        assert app.state.database is factory.resources
        assert client.get("/health").status_code == 200
    assert app.state.database is None
    assert factory.closed


def test_unavailable_database_returns_redacted_503(fake_readiness):
    from psycopg import OperationalError

    fake_readiness.side_effect = OperationalError("fixture-secret")
    with TestClient(create_app(database_factory=FakeDatabaseFactory())) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "database_unavailable"}
        assert "fixture-secret" not in response.text


def test_default_lifespan_rejects_missing_credentials():
    with (
        pytest.raises(ValueError, match="KNOWLEDGE_DB_PASSWORD"),
        TestClient(create_app()),
    ):
        pass

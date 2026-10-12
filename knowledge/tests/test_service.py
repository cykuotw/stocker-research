"""Verify that Knowledge startup is independent of the copied Agent runtime."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from knowledge.app.core.factory import create_app
from knowledge.config.app import AppSettings


def test_service_starts_without_agent_database_skills_or_models(monkeypatch):
    monkeypatch.setenv("DB_NAME", "stocker_agent_runtime")
    monkeypatch.setenv("SKILL_MODE", "s3")
    with (
        patch("socket.socket.connect", side_effect=AssertionError("network access")),
        TestClient(create_app()) as client,
    ):
        assert client.get("/health").json() == {"status": "ok"}
        info = client.get("/info").json()
        assert info["service"] == "stocker-knowledge"
        assert info["implemented_capabilities"] == ["health", "service_info"]
        assert "retrieval" in info["planned_capabilities"]
        assert "mcp" in info["planned_capabilities"]
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "Stocker Knowledge Service"
        assert set(schema["paths"]) == {"/health", "/info"}


@pytest.mark.parametrize(
    "path", ["/api/graphs", "/api/assistants", "/api/sessions", "/mcp"]
)
def test_copied_runtime_and_unimplemented_mcp_are_not_exposed(path):
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


def test_configured_cors_allows_only_selected_origins():
    app = create_app(AppSettings(cors_origins=["https://consumer.example"]))
    with TestClient(app) as client:
        allowed = client.get("/info", headers={"Origin": "https://consumer.example"})
        denied = client.get("/info", headers={"Origin": "https://other.example"})
        assert (
            allowed.headers["access-control-allow-origin"] == "https://consumer.example"
        )
        assert "access-control-allow-origin" not in denied.headers

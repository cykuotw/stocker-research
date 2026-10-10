"""HTTP injection and resource lifecycle tests without credentials or model calls."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from stocker_agent.app.context import AppContext
from stocker_agent.app.dependencies import get_context, get_runner, get_service
from stocker_agent.app.errors import RuntimeProblem
from stocker_agent.app.factory import create_app
from stocker_agent.app.models import Run, RuntimeEvent
from stocker_agent.config.app import AppSettings


@asynccontextmanager
async def no_resources(app):
    yield


def isolated_app():
    return create_app(AppSettings(), lifespan=no_resources)


def run_record():
    return Run(
        run_id=uuid4(),
        session_id=uuid4(),
        status="completed",
        action="input",
        idempotency_key="test",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_override_service_without_database():
    service = Mock(graph_ids=Mock(return_value=["echo"]))
    app = isolated_app()
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        assert client.get("/api/graphs").json() == ["echo"]
        assert client.get("/info").json()["tracing"] is False
    service.graph_ids.assert_called_once_with()


def test_uninitialized_context_returns_service_unavailable():
    with TestClient(isolated_app()) as client:
        response = client.get("/api/graphs")
        assert response.status_code == 503
        assert response.json() == {"error": {"code": "runtime_unavailable"}}


def test_cancel_uses_runner_dependency():
    record = run_record()
    runner = Mock(cancel=AsyncMock(return_value=record.model_dump()))
    app = isolated_app()
    app.dependency_overrides[get_runner] = lambda: runner
    with TestClient(app) as client:
        assert client.post(f"/api/runs/{record.run_id}/cancel").status_code == 200
    runner.cancel.assert_awaited_once_with(record.run_id)


def test_missing_run_fails_before_stream_headers():
    service = Mock(run=AsyncMock(side_effect=RuntimeProblem("not_found", 404)))
    app = isolated_app()
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        response = client.get(f"/api/runs/{uuid4()}/events/stream")
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"error": {"code": "not_found"}}


def test_stream_reconnect_cursor_and_request_dependency_cache():
    record = run_record()
    event = RuntimeEvent(
        event_id=12,
        session_id=record.session_id,
        run_id=record.run_id,
        kind="run.completed",
        created_at=datetime.now(UTC),
        payload={},
    )
    cursors = []

    async def events(run_id, after):
        assert run_id == record.run_id
        cursors.append(after)
        yield event

    service = Mock(run=AsyncMock(return_value=record), stream_events=events)
    runner = Mock()
    context = AppContext(AppSettings(), service, runner, 123)
    calls = []

    async def context_override():
        calls.append(True)
        return context

    app = isolated_app()
    app.dependency_overrides[get_context] = context_override
    with TestClient(app) as client:
        response = client.get(
            f"/api/runs/{record.run_id}/events/stream?after=3",
            headers={"Last-Event-ID": "11"},
        )
        assert response.status_code == 200
        assert "id: 12" in response.text
        assert "event: run.completed" in response.text
    assert cursors == [11]
    assert calls == [True]
    service.run.assert_awaited_once_with(record.run_id)


def test_health_checks_injected_worker_and_repository():
    service = Mock(ready=AsyncMock())
    runner = Mock(failure=None)
    app = isolated_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_runner] = lambda: runner
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        runner.failure = "ownership_connection_lost"
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "worker_unavailable"
    service.ready.assert_awaited_once_with()


def test_missing_credentials_fail_startup_not_assembly(monkeypatch):
    for key in ("DATABASE_URI", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    app = create_app(AppSettings())
    with pytest.raises(ValueError, match="Set DB_PASSWORD"), TestClient(app):
        pass


def test_lifespan_shares_settings_and_stops_worker_before_pools(monkeypatch):
    from stocker_agent.app import lifespan as lifecycle

    order = []
    config = AppSettings(database_uri="postgresql://localhost/stocker_agent_runtime")
    owner = Mock(info=SimpleNamespace(backend_pid=123))
    cursor = Mock(fetchone=AsyncMock(return_value={"acquired": True}))
    owner.execute = AsyncMock(return_value=cursor)

    @asynccontextmanager
    async def owner_context():
        yield owner
        order.append("owner_closed")

    connection = MagicMock()
    connection.__getitem__ = Mock(return_value=connection)
    connection.connect = AsyncMock(return_value=owner_context())
    monkeypatch.setattr(lifecycle, "AsyncConnection", connection)

    class Pool:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, *args, **kwargs):
            self.name = "checkpoint" if "options" in kwargs["kwargs"] else "runtime"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            order.append(self.name + "_closed")

        async def wait(self):
            pass

    repository = Mock(migrate=AsyncMock(), recover_abandoned=AsyncMock())
    saver = Mock(setup=AsyncMock())
    runner = Mock(
        start=Mock(), stop=AsyncMock(side_effect=lambda: order.append("worker_stopped"))
    )
    monkeypatch.setattr(lifecycle, "AsyncConnectionPool", Pool)
    monkeypatch.setattr(lifecycle, "RuntimeRepository", lambda pool: repository)
    monkeypatch.setattr(lifecycle, "AsyncPostgresSaver", lambda pool: saver)
    monkeypatch.setattr(lifecycle, "GraphRunner", lambda service, poll: runner)
    factory = Mock(return_value=Mock())
    app = create_app(config, {"echo": factory})
    with TestClient(app):
        assert app.state.context.settings is config
        assert app.state.context.runner is runner
        assert app.state.context.ownership_pid == 123
        runner.start.assert_called_once()
        repository.recover_abandoned.assert_awaited_once()
        factory.assert_called_once_with(saver)
    assert app.state.context is None
    assert order == [
        "worker_stopped",
        "checkpoint_closed",
        "runtime_closed",
        "owner_closed",
    ]

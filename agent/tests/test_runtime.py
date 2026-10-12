"""Real PostgreSQL integration, opt in with TEST_RUNTIME_DATABASE_URI."""

import asyncio
import os
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from graph_fixtures import build_test_resources
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from stocker_agent.app.core.factory import create_app
from stocker_agent.app.database.factory import DatabaseFactory
from stocker_agent.app.models import AssistantInput, RunInput, SessionInput
from stocker_agent.app.repositories.runtime import RuntimeRepository
from stocker_agent.app.utils.serialization import public_data
from stocker_agent.config.app import AppSettings


def deterministic(resources):
    saver = resources.checkpointer

    async def reply(state):
        text = state["messages"][-1].content
        if text == "brief":
            await asyncio.sleep(0.3)
        if text == "slow":
            await asyncio.sleep(30)
        if text == "fail":
            raise ValueError("never expose private error details")
        return {"messages": [AIMessage(content="reply: " + text)]}

    return (
        StateGraph(MessagesState)
        .add_node("reply", reply)
        .add_edge(START, "reply")
        .add_edge("reply", END)
        .compile(checkpointer=saver)
    )


REVIEW_ENTRIES = []


def review(resources):
    saver = resources.checkpointer

    def ask(state):
        REVIEW_ENTRIES.append(True)
        approved = interrupt({"question": "approve?"})
        return {"messages": [AIMessage(content=str(approved))]}

    return (
        StateGraph(MessagesState)
        .add_node("review", ask)
        .add_edge(START, "review")
        .add_edge("review", END)
        .compile(checkpointer=saver)
    )


@pytest.fixture
def settings():
    uri = os.environ.get("TEST_RUNTIME_DATABASE_URI")
    if not uri:
        pytest.skip("Set TEST_RUNTIME_DATABASE_URI for PostgreSQL integration")
    return AppSettings(database_uri=uri, poll_seconds=0.02)


def app(settings):
    return create_app(
        settings,
        {"echo": deterministic, "review": review},
        graph_resources_factory=build_test_resources,
    )


def session(client, graph="echo"):
    result = client.post(
        "/api/assistants",
        json={"graph_id": graph, "name": "integration " + str(uuid4())},
    )
    assert result.status_code == 201, result.text
    result = client.post(
        "/api/sessions", json={"assistant_id": result.json()["assistant_id"]}
    )
    assert result.status_code == 201, result.text
    return result.json()["session_id"]


def submit(client, sid, text, key=None):
    body = {
        "input": {"messages": [{"role": "user", "content": text}]},
        "idempotency_key": key or str(uuid4()),
    }
    result = client.post(f"/api/sessions/{sid}/runs", json=body)
    assert result.status_code == 202, result.text
    return result.json()["run_id"], body


def wait(client, rid, status="completed"):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get(f"/api/runs/{rid}").json()
        if result["status"] == status:
            return result
        if result["status"] in ("failed", "cancelled") and status not in (
            "failed",
            "cancelled",
        ):
            pytest.fail(str(result))
        time.sleep(0.02)
    pytest.fail("run did not reach " + status)


def test_validation_and_redaction(monkeypatch):
    with pytest.raises(ValidationError):
        RunInput(action="resume", idempotency_key="a")
    assert RunInput(action="resume", resume=None, idempotency_key="a").resume is None
    with pytest.raises(ValidationError):
        AppSettings(database_uri="postgresql://localhost/expense_tracker")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-secret-value")
    assert public_data(
        {"api_key": "test-secret-value", "text": "contains test-secret-value"}
    ) == {"api_key": "[redacted]", "text": "contains [redacted]"}


def test_two_turns_restart_events_and_checkpoints(settings):
    with TestClient(app(settings)) as client:
        sid = session(client)
        rid, body = submit(client, sid, "one")
        wait(client, rid)
        retry = client.post(f"/api/sessions/{sid}/runs", json=body)
        assert retry.json()["run_id"] == rid
        changed = {
            **body,
            "input": {"messages": [{"role": "user", "content": "different"}]},
        }
        assert client.post(f"/api/sessions/{sid}/runs", json=changed).status_code == 409
        rid2, _ = submit(client, sid, "two")
        wait(client, rid2)
        assert rid != rid2
        events = client.get(f"/api/runs/{rid2}/events?limit=200").json()
        assert events[-1]["kind"] == "run.completed"
        cursor = events[1]["event_id"]
        assert (
            client.get(f"/api/runs/{rid2}/events?after={cursor}").json() == events[2:]
        )
        stream = client.get(
            f"/api/runs/{rid2}/events/stream", headers={"Last-Event-ID": str(cursor)}
        )
        assert stream.status_code == 200
        assert "id: " + str(events[0]["event_id"]) + "\n" not in stream.text
        assert "run.completed" in stream.text
        history = client.get(f"/api/sessions/{sid}/checkpoints").json()
        assert len(history) >= 6
        left, right = history[-1]["checkpoint_id"], history[0]["checkpoint_id"]
        comparison = client.get(
            f"/api/sessions/{sid}/checkpoints/compare",
            params={"left": left, "right": right},
        ).json()
        assert "messages" in comparison["changed_keys"]
    with TestClient(app(settings)) as client:
        state = client.get(f"/api/sessions/{sid}/state").json()
        assert [m["content"] for m in state["values"]["messages"]] == [
            "one",
            "reply: one",
            "two",
            "reply: two",
        ]
        assert client.get(f"/api/sessions/{sid}/runs").json()
        assert client.get(f"/api/runs/{rid2}").json()["status"] == "completed"
        assert client.get("/info").json()["tracing"] is False
        assert (
            "/api/sessions/{session_id}/runs"
            in client.get("/openapi.json").json()["paths"]
        )


def test_interrupt_survives_restart(settings):
    REVIEW_ENTRIES.clear()
    with TestClient(app(settings)) as client:
        sid = session(client, "review")
        rid, _ = submit(client, sid, "question")
        wait(client, rid, "interrupted")
        assert client.get(f"/api/sessions/{sid}/state").json()["interrupts"]
    with TestClient(app(settings)) as client:
        result = client.post(
            f"/api/sessions/{sid}/runs",
            json={"action": "resume", "resume": True, "idempotency_key": str(uuid4())},
        )
        assert result.status_code == 202, result.text
        wait(client, result.json()["run_id"])
        assert (
            client.get(f"/api/sessions/{sid}/state").json()["values"]["messages"][-1][
                "content"
            ]
            == "True"
        )
        assert len(REVIEW_ENTRIES) == 2


def test_conflict_cancel_and_shutdown_recovery(settings):
    with TestClient(app(settings)) as client:
        sid = session(client)
        rid, _ = submit(client, sid, "slow")
        wait(client, rid, "running")
        assert (
            client.post(
                f"/api/sessions/{sid}/runs",
                json={"input": {}, "idempotency_key": str(uuid4())},
            ).status_code
            == 409
        )
        assert client.post(f"/api/runs/{rid}/cancel").json()["status"] == "cancelled"
        other = session(client)
        abandoned, _ = submit(client, other, "slow")
        wait(client, abandoned, "running")
        # The claim commits before graph execution writes its first checkpoint.
        for _ in range(100):
            if client.get(f"/api/sessions/{other}/state").json()["next"] == ["reply"]:
                break
            time.sleep(0.02)
        else:
            pytest.fail("Graph did not persist its unfinished-node checkpoint")
    with TestClient(app(settings)) as client:
        assert (
            client.get(f"/api/runs/{abandoned}").json()["status"] == "recovery_required"
        )
        assert (
            client.post(
                f"/api/sessions/{other}/runs",
                json={"input": {}, "idempotency_key": str(uuid4())},
            ).status_code
            == 409
        )
        # A checkpoint with an unfinished node is retained, without automatic replay.
        assert client.get(f"/api/sessions/{other}/state").json()["next"] == ["reply"]
        assert client.get("/health").status_code == 200


def test_failure_is_safe_and_worker_continues(settings):
    with TestClient(app(settings)) as client:
        sid = session(client)
        rid, _ = submit(client, sid, "fail")
        result = wait(client, rid, "failed")
        assert result["error"] == {
            "code": "graph_execution_failed",
            "exception_type": "ValueError",
        }
        sid2 = session(client)
        rid2, _ = submit(client, sid2, "works")
        wait(client, rid2)


def test_single_owner_and_static_fallback(settings, tmp_path):
    (tmp_path / "index.html").write_text("<html>test UI</html>")
    settings.static_directory = tmp_path
    with TestClient(app(settings)) as client:
        with (
            pytest.raises(Exception, match="runtime_already_running"),
            TestClient(app(settings)),
        ):
            pass
        assert (
            "test UI"
            in client.get("/sessions/example", headers={"Accept": "text/html"}).text
        )
        assert (
            client.get("/api/missing", headers={"Accept": "text/html"}).status_code
            == 404
        )
        assert client.get("/health").json()["status"] == "ok"
    settings.static_directory = tmp_path / "missing"
    with TestClient(app(settings)) as client:
        assert client.get("/health").status_code == 200


def recovery_graph(resources):
    saver = resources.checkpointer
    """A completed side effect followed by a blocking node, for real process death."""
    from pathlib import Path

    def prepare(state):
        marker = Path(os.environ["RUNTIME_TEST_EFFECT"])
        count = int(marker.read_text()) if marker.exists() else 0
        marker.write_text(str(count + 1))
        return {"messages": [AIMessage(content="prepared")]}

    async def finish(state):
        if os.environ.get("RUNTIME_TEST_FINISH") != "true":
            await asyncio.sleep(60)
        return {"messages": [AIMessage(content="finished")]}

    return (
        StateGraph(MessagesState)
        .add_node("prepare", prepare)
        .add_node("finish", finish)
        .add_edge(START, "prepare")
        .add_edge("prepare", "finish")
        .add_edge("finish", END)
        .compile(checkpointer=saver)
    )


def test_pending_and_abrupt_restart_with_explicit_recovery(
    settings, tmp_path, monkeypatch
):
    import subprocess
    import sys
    from pathlib import Path

    import psycopg
    from psycopg.rows import dict_row

    effect = tmp_path / "effect.txt"
    monkeypatch.setenv("RUNTIME_TEST_EFFECT", str(effect))
    # Persist a submission while the worker is stopped, simulating queued work at shutdown.
    with TestClient(
        create_app(
            settings,
            {"crash": recovery_graph},
            graph_resources_factory=build_test_resources,
        )
    ) as client:
        client.portal.call(client.app.state.context.runner.stop)
        sid = session(client, "crash")
        rid, _ = submit(client, sid, "start")
        assert client.get(f"/api/runs/{rid}").json()["status"] == "pending"

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parent.resolve())
    code = """import asyncio,os
from stocker_agent.config import base
base.ENV_FILE=None
from test_runtime import recovery_graph
from graph_fixtures import build_test_resources
from stocker_agent.config.app import AppSettings
from stocker_agent.app.core.factory import create_app
async def main():
    app=create_app(AppSettings(database_uri=os.environ['TEST_RUNTIME_DATABASE_URI'],poll_seconds=.02),{'crash':recovery_graph}, graph_resources_factory=build_test_resources)
    async with app.router.lifespan_context(app):
        await asyncio.Event().wait()
asyncio.run(main())
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        with psycopg.connect(
            settings.conninfo(), row_factory=dict_row, autocommit=True
        ) as conn:
            while time.monotonic() < deadline:
                row = conn.execute(
                    "SELECT status FROM runtime.runs WHERE run_id=%s", (rid,)
                ).fetchone()
                checkpoints = conn.execute(
                    "SELECT checkpoint FROM checkpoints.checkpoints WHERE thread_id=%s ORDER BY checkpoint_id DESC LIMIT 1",
                    (sid,),
                ).fetchone()
                if (
                    row["status"] == "running"
                    and effect.exists()
                    and checkpoints
                    and checkpoints["checkpoint"]["channel_values"].get(
                        "branch:to:finish"
                    )
                    is not None
                ):
                    break
                # Inspect graph checkpoints rather than relying on time alone.
                if (
                    row["status"] == "running"
                    and effect.exists()
                    and checkpoints
                    and checkpoints["checkpoint"]["channel_versions"].get(
                        "branch:to:finish"
                    )
                ):
                    break
                assert process.poll() is None, "child runtime exited before checkpoint"
                time.sleep(0.02)
            else:
                pytest.fail("child did not persist the completed prepare node")
        process.kill()
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    monkeypatch.setenv("RUNTIME_TEST_FINISH", "true")
    with TestClient(
        create_app(
            settings,
            {"crash": recovery_graph},
            graph_resources_factory=build_test_resources,
        )
    ) as client:
        assert client.get(f"/api/runs/{rid}").json()["status"] == "recovery_required"
        assert effect.read_text() == "1"
        assert client.get(f"/api/sessions/{sid}/state").json()["next"] == ["finish"]
        result = client.post(
            f"/api/sessions/{sid}/runs",
            json={
                "action": "recover",
                "acknowledge_replay": True,
                "idempotency_key": str(uuid4()),
            },
        )
        assert result.status_code == 202, result.text
        wait(client, result.json()["run_id"])
        assert effect.read_text() == "1"
        assert (
            client.get(f"/api/sessions/{sid}/state").json()["values"]["messages"][-1][
                "content"
            ]
            == "finished"
        )


def test_real_echo_factory_tools_and_model_events(settings):
    from unittest.mock import Mock

    from test_echo_graph import ToolCallingModel, sample_skill

    from stocker_agent.graphs.echo import build_echo_graph

    def factory(resources):
        saver = resources.checkpointer
        registry, models = Mock(), Mock()
        registry.get.return_value = sample_skill()
        models.get.return_value = ToolCallingModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "print_user_message",
                            "args": {"message": "hello"},
                            "id": "greeting-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="Echo: hello"),
            ]
        )
        return build_echo_graph(
            build_test_resources(saver, skills=registry, models=models)
        )

    with TestClient(
        create_app(
            settings, {"echo": factory}, graph_resources_factory=build_test_resources
        )
    ) as client:
        sid = session(client)
        rid, _ = submit(client, sid, "hello")
        wait(client, rid)
        assert (
            client.get(f"/api/sessions/{sid}/state").json()["values"]["messages"][-1][
                "content"
            ]
            == "Echo: hello"
        )
        events = client.get(f"/api/runs/{rid}/events?limit=200").json()
        kinds = {record["kind"] for record in events}
        assert {
            "on_tool_start",
            "on_tool_end",
            "on_chat_model_start",
            "on_chat_model_end",
        } <= kinds


def test_stream_request_validation(settings):
    with TestClient(app(settings)) as client:
        sid = session(client)
        rid, _ = submit(client, sid, "one")
        wait(client, rid)
        assert client.get(f"/api/runs/{uuid4()}/events/stream").status_code == 404
        for header in ("invalid", "-1"):
            result = client.get(
                f"/api/runs/{rid}/events/stream", headers={"Last-Event-ID": header}
            )
            assert result.status_code == 422


def test_client_disconnect_keeps_run_alive(settings):
    import socket
    import subprocess
    import sys
    from pathlib import Path

    import httpx

    # Pass a prebound loopback socket to avoid a free-port allocation race.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).parent.resolve())
        env["RUNTIME_TEST_LISTENER"] = str(listener.fileno())
        code = """import os,uvicorn
from stocker_agent.config import base
base.ENV_FILE=None
from test_runtime import deterministic
from graph_fixtures import build_test_resources
from stocker_agent.config.app import AppSettings
from stocker_agent.app.core.factory import create_app
app=create_app(AppSettings(database_uri=os.environ['TEST_RUNTIME_DATABASE_URI'],poll_seconds=.02),{'echo':deterministic}, graph_resources_factory=build_test_resources)
uvicorn.run(app,fd=int(os.environ['RUNTIME_TEST_LISTENER']),log_level='critical')
"""
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            env=env,
            pass_fds=(listener.fileno(),),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert process.poll() is None, "test server exited before startup"
                    time.sleep(0.05)
                else:
                    pytest.fail("HTTP server did not become ready")
                sid = session(client)
                rid, _ = submit(client, sid, "brief")
                with client.stream("GET", f"/api/runs/{rid}/events/stream") as response:
                    assert response.status_code == 200
                    for line in response.iter_lines():
                        if line.startswith("id:"):
                            break
                wait(client, rid)
                assert (
                    client.get(f"/api/sessions/{sid}/state").json()["values"][
                        "messages"
                    ][-1]["content"]
                    == "reply: brief"
                )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def test_lost_ownership_stops_worker(settings):
    import psycopg

    with TestClient(app(settings)) as client:
        sid = session(client)
        rid, _ = submit(client, sid, "slow")
        wait(client, rid, "running")
        with psycopg.connect(settings.conninfo(), autocommit=True) as conn:
            # Only terminate this test server's own lock connection, never another service.
            assert conn.execute(
                "SELECT pg_terminate_backend(%s)",
                (client.app.state.context.ownership_pid,),
            ).fetchone()[0]
        wait(client, rid, "recovery_required")
        assert client.get("/health").status_code == 503
        with TestClient(app(settings)) as replacement:
            assert replacement.get("/health").status_code == 200
            assert (
                replacement.get(f"/api/runs/{rid}").json()["status"]
                == "recovery_required"
            )


@pytest.mark.asyncio
async def test_sqlalchemy_rolls_back_run_when_event_write_fails(settings, monkeypatch):
    from unittest.mock import AsyncMock

    async with DatabaseFactory().open(settings) as database:
        repository = RuntimeRepository(database.engine)
        await repository.migrate()
        assistant = await repository.assistant(
            AssistantInput(graph_id="echo", name="rollback")
        )
        record = await repository.session(
            SessionInput(assistant_id=assistant["assistant_id"])
        )
        sid = record["session_id"]
        monkeypatch.setattr(
            repository,
            "_event",
            AsyncMock(side_effect=RuntimeError("fixture event failure")),
        )
        with pytest.raises(RuntimeError, match="fixture event failure"):
            await repository.enqueue(
                sid, RunInput(input={"messages": []}, idempotency_key="rollback")
            )
        assert await repository.list_runs(sid, None, 10) == []
        assert await repository.session_events(sid, 0, 10) == []


def test_sql_like_values_round_trip_without_execution(settings):
    malicious = "'); DROP SCHEMA runtime CASCADE; --"
    with TestClient(app(settings)) as client:
        assistant = client.post(
            "/api/assistants", json={"graph_id": "echo", "name": malicious}
        ).json()
        assert assistant["name"] == malicious
        record = client.post(
            "/api/sessions",
            json={"assistant_id": assistant["assistant_id"], "title": malicious},
        ).json()
        assert record["title"] == malicious
        run_id, body = submit(client, record["session_id"], malicious, key=malicious)
        wait(client, run_id, "completed")
        replay = client.post(f"/api/sessions/{record['session_id']}/runs", json=body)
        assert replay.json()["run_id"] == run_id
        state = client.get(f"/api/sessions/{record['session_id']}/state").json()
        assert state["values"]["messages"][-1]["content"] == "reply: " + malicious
        assert client.get("/api/assistants").status_code == 200

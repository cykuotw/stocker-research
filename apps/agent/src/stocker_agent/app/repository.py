"""Transactional runtime metadata; checkpoints are managed by LangGraph."""

from hashlib import sha256
from pathlib import Path
from typing import Any, LiteralString, cast
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.sql import SQL
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from stocker_agent.app.errors import RuntimeProblem
from stocker_agent.app.models import AssistantInput, RunInput, SessionInput
from stocker_agent.app.serialization import public_data


class RuntimeRepository:
    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]]):
        self.pool = pool

    async def ready(self) -> None:
        await self._one("SELECT 1 AS ready")

    async def get_assistant(self, assistant_id: UUID) -> dict:
        return await self._one(
            "SELECT * FROM runtime.assistants WHERE assistant_id=%s", (assistant_id,)
        )

    async def list_assistants(self, after: UUID | None, limit: int) -> list[dict]:
        return await self._rows(
            "SELECT * FROM runtime.assistants WHERE (%s::uuid IS NULL OR assistant_id>%s) ORDER BY assistant_id LIMIT %s",
            (after, after, limit),
        )

    async def get_session(self, session_id: UUID) -> dict:
        return await self._one(
            "SELECT * FROM runtime.sessions WHERE session_id=%s", (session_id,)
        )

    async def list_sessions(self, after: UUID | None, limit: int) -> list[dict]:
        return await self._rows(
            "SELECT * FROM runtime.sessions WHERE (%s::uuid IS NULL OR session_id>%s) ORDER BY session_id LIMIT %s",
            (after, after, limit),
        )

    async def get_run(self, run_id: UUID) -> dict:
        return await self._one("SELECT * FROM runtime.runs WHERE run_id=%s", (run_id,))

    async def list_runs(
        self, session_id: UUID, after: UUID | None, limit: int
    ) -> list[dict]:
        return await self._rows(
            "SELECT * FROM runtime.runs WHERE session_id=%s AND (%s::uuid IS NULL OR run_id>%s) ORDER BY run_id LIMIT %s",
            (session_id, after, after, limit),
        )

    async def run_events(self, run_id: UUID, after: int, limit: int) -> list[dict]:
        return await self._rows(
            "SELECT * FROM runtime.events WHERE run_id=%s AND event_id>%s ORDER BY event_id LIMIT %s",
            (run_id, after, limit),
        )

    async def session_events(
        self, session_id: UUID, after: int, limit: int
    ) -> list[dict]:
        return await self._rows(
            "SELECT * FROM runtime.events WHERE session_id=%s AND event_id>%s ORDER BY event_id LIMIT %s",
            (session_id, after, limit),
        )

    async def migrate(self):
        sql = (Path(__file__).parent / "migrations/001_runtime.sql").read_text()
        checksum = sha256(sql.encode()).hexdigest()
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(SQL(cast(LiteralString, sql)), prepare=False)
            row = await (
                await conn.execute(
                    "SELECT checksum FROM runtime.schema_migrations WHERE version=1"
                )
            ).fetchone()
            if row and row["checksum"] != checksum:
                raise RuntimeProblem("migration_checksum_mismatch", 500)
            await conn.execute(
                "INSERT INTO runtime.schema_migrations(version,checksum) VALUES (1,%s) ON CONFLICT DO NOTHING",
                (checksum,),
            )

    async def _rows(self, sql: LiteralString, params: tuple = ()) -> list[dict]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchall()

    async def _one(self, sql: LiteralString, params: tuple = ()) -> dict:
        rows = await self._rows(sql, params)
        if not rows:
            raise RuntimeProblem("not_found", 404)
        return rows[0]

    async def assistant(self, body: AssistantInput) -> dict:
        return await self._one(
            "INSERT INTO runtime.assistants(assistant_id,graph_id,name,config) VALUES (%s,%s,%s,%s) RETURNING *",
            (uuid4(), body.graph_id, body.name, Jsonb(body.config.model_dump())),
        )

    async def session(self, body: SessionInput) -> dict:
        assistant = await self._one(
            "SELECT * FROM runtime.assistants WHERE assistant_id=%s",
            (body.assistant_id,),
        )
        return await self._one(
            "INSERT INTO runtime.sessions(session_id,assistant_id,graph_id,config,title) VALUES (%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid4(),
                body.assistant_id,
                assistant["graph_id"],
                Jsonb(assistant["config"]),
                body.title,
            ),
        )

    async def enqueue(self, session_id: UUID, body: RunInput) -> dict:
        request = body.model_dump(mode="json", exclude_unset=True)
        async with self.pool.connection() as conn, conn.transaction():
            session = await (
                await conn.execute(
                    "SELECT session_id FROM runtime.sessions WHERE session_id=%s FOR UPDATE",
                    (session_id,),
                )
            ).fetchone()
            if not session:
                raise RuntimeProblem("not_found", 404)
            existing = await (
                await conn.execute(
                    "SELECT * FROM runtime.runs WHERE session_id=%s AND idempotency_key=%s",
                    (session_id, body.idempotency_key),
                )
            ).fetchone()
            if existing:
                if existing["request"]["submission"] != request:
                    raise RuntimeProblem("idempotency_conflict")
                return existing
            latest = await (
                await conn.execute(
                    "SELECT * FROM runtime.runs WHERE session_id=%s ORDER BY created_at DESC,run_id DESC LIMIT 1",
                    (session_id,),
                )
            ).fetchone()
            status = latest["status"] if latest else None
            if status in ("pending", "running"):
                raise RuntimeProblem("session_busy")
            if body.action == "resume" and status != "interrupted":
                raise RuntimeProblem("session_not_interrupted")
            if body.action == "recover" and status not in (
                "recovery_required",
                "failed",
                "cancelled",
            ):
                raise RuntimeProblem("session_not_recoverable")
            if body.action == "input" and status in (
                "interrupted",
                "recovery_required",
                "failed",
                "cancelled",
            ):
                raise RuntimeProblem("resume_or_recover_required")
            stored = {"submission": request}
            if body.action == "recover":
                assert latest is not None
                stored["source_run_ids"] = [
                    *latest["request"].get("source_run_ids", []),
                    str(latest["run_id"]),
                ]
                stored["source"] = latest["request"].get(
                    "source", latest["request"]["submission"]
                )
            row = await (
                await conn.execute(
                    "INSERT INTO runtime.runs(run_id,session_id,action,request,idempotency_key,status,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,'pending',clock_timestamp(),clock_timestamp()) RETURNING *",
                    (
                        uuid4(),
                        session_id,
                        body.action,
                        Jsonb(stored),
                        body.idempotency_key,
                    ),
                )
            ).fetchone()
            assert row is not None
            await self._event(conn, row, "run.pending", {})
            return row

    async def _event(
        self,
        conn: AsyncConnection[dict[str, Any]],
        run: dict,
        kind: str,
        payload: object,
    ):
        await conn.execute(
            "INSERT INTO runtime.events(session_id,run_id,kind,payload) VALUES (%s,%s,%s,%s)",
            (run["session_id"], run["run_id"], kind, Jsonb(public_data(payload))),
        )

    async def event(self, run: dict, kind: str, payload: object):
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "SELECT * FROM runtime.runs WHERE run_id=%s FOR UPDATE",
                    (run["run_id"],),
                )
            ).fetchone()
            if row and row["status"] == "running":
                await self._event(conn, row, kind, payload)

    async def transition(
        self, run_id: UUID, status: str, error: dict | None = None
    ) -> dict:
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "SELECT * FROM runtime.runs WHERE run_id=%s FOR UPDATE", (run_id,)
                )
            ).fetchone()
            if not row:
                raise RuntimeProblem("not_found", 404)
            if row["status"] not in ("pending", "running"):
                return row
            row = await (
                await conn.execute(
                    "UPDATE runtime.runs SET status=%s,error=%s,updated_at=clock_timestamp() WHERE run_id=%s RETURNING *",
                    (status, Jsonb(error) if error else None, run_id),
                )
            ).fetchone()
            assert row is not None
            await self._event(
                conn, row, f"run.{status}", {"status": status, "error": error}
            )
            return row

    async def recover_abandoned(self):
        for row in await self._rows(
            "SELECT run_id FROM runtime.runs WHERE status='running'"
        ):
            await self.transition(row["run_id"], "recovery_required")

    async def claim(self) -> dict | None:
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "SELECT * FROM runtime.runs WHERE status='pending' ORDER BY created_at,run_id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).fetchone()
            if row:
                row = await (
                    await conn.execute(
                        "UPDATE runtime.runs SET status='running',updated_at=clock_timestamp() WHERE run_id=%s RETURNING *",
                        (row["run_id"],),
                    )
                ).fetchone()
                assert row is not None
                await self._event(conn, row, "run.running", {"status": "running"})
            return row

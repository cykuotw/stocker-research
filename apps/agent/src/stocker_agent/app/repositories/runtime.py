"""SQLAlchemy Core runtime metadata queries; LangGraph owns checkpoints."""

from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import Executable, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from stocker_agent.app.core.errors import RuntimeProblem
from stocker_agent.app.database.migrations import migrate_runtime
from stocker_agent.app.database.tables import assistants, events, runs, sessions
from stocker_agent.app.models import AssistantInput, RunInput, SessionInput
from stocker_agent.app.utils.serialization import public_data


async def fetch_one(conn: AsyncConnection, statement: Executable) -> dict | None:
    row = (await conn.execute(statement)).mappings().first()
    return dict(row) if row is not None else None


class RuntimeRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def ready(self) -> None:
        await self._one(select(1))

    async def get_assistant(self, assistant_id: UUID) -> dict:
        return await self._one(
            select(assistants).where(assistants.c.assistant_id == assistant_id)
        )

    async def list_assistants(self, after: UUID | None, limit: int) -> list[dict]:
        statement = select(assistants).order_by(assistants.c.assistant_id).limit(limit)
        if after is not None:
            statement = statement.where(assistants.c.assistant_id > after)
        return await self._rows(statement)

    async def get_session(self, session_id: UUID) -> dict:
        return await self._one(
            select(sessions).where(sessions.c.session_id == session_id)
        )

    async def list_sessions(self, after: UUID | None, limit: int) -> list[dict]:
        statement = select(sessions).order_by(sessions.c.session_id).limit(limit)
        if after is not None:
            statement = statement.where(sessions.c.session_id > after)
        return await self._rows(statement)

    async def get_run(self, run_id: UUID) -> dict:
        return await self._one(select(runs).where(runs.c.run_id == run_id))

    async def list_runs(
        self, session_id: UUID, after: UUID | None, limit: int
    ) -> list[dict]:
        statement = (
            select(runs)
            .where(runs.c.session_id == session_id)
            .order_by(runs.c.run_id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(runs.c.run_id > after)
        return await self._rows(statement)

    async def run_events(self, run_id: UUID, after: int, limit: int) -> list[dict]:
        return await self._rows(
            select(events)
            .where(events.c.run_id == run_id, events.c.event_id > after)
            .order_by(events.c.event_id)
            .limit(limit)
        )

    async def session_events(
        self, session_id: UUID, after: int, limit: int
    ) -> list[dict]:
        return await self._rows(
            select(events)
            .where(events.c.session_id == session_id, events.c.event_id > after)
            .order_by(events.c.event_id)
            .limit(limit)
        )

    async def migrate(self):
        async with self.engine.begin() as conn:
            await migrate_runtime(conn)

    async def _rows(self, statement: Executable) -> list[dict]:
        async with self.engine.begin() as conn:
            return [
                dict(row) for row in (await conn.execute(statement)).mappings().all()
            ]

    async def _one(self, statement: Executable) -> dict:
        rows = await self._rows(statement)
        if not rows:
            raise RuntimeProblem("not_found", 404)
        return rows[0]

    async def assistant(self, body: AssistantInput) -> dict:
        return await self._one(
            insert(assistants)
            .values(
                assistant_id=uuid4(),
                graph_id=body.graph_id,
                name=body.name,
                config=body.config.model_dump(),
            )
            .returning(assistants)
        )

    async def session(self, body: SessionInput) -> dict:
        assistant = await self.get_assistant(body.assistant_id)
        return await self._one(
            insert(sessions)
            .values(
                session_id=uuid4(),
                assistant_id=body.assistant_id,
                graph_id=assistant["graph_id"],
                config=assistant["config"],
                title=body.title,
            )
            .returning(sessions)
        )

    async def enqueue(self, session_id: UUID, body: RunInput) -> dict:
        request = body.model_dump(mode="json", exclude_unset=True)
        async with self.engine.begin() as conn:
            session = await fetch_one(
                conn,
                select(sessions.c.session_id)
                .where(sessions.c.session_id == session_id)
                .with_for_update(),
            )
            if session is None:
                raise RuntimeProblem("not_found", 404)
            existing = await fetch_one(
                conn,
                select(runs).where(
                    runs.c.session_id == session_id,
                    runs.c.idempotency_key == body.idempotency_key,
                ),
            )
            if existing is not None:
                if existing["request"]["submission"] != request:
                    raise RuntimeProblem("idempotency_conflict")
                return existing
            latest = await fetch_one(
                conn,
                select(runs)
                .where(runs.c.session_id == session_id)
                .order_by(runs.c.created_at.desc(), runs.c.run_id.desc())
                .limit(1),
            )
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
            stored: dict[str, JsonValue] = {"submission": request}
            if body.action == "recover":
                assert latest is not None
                stored["source_run_ids"] = [
                    *latest["request"].get("source_run_ids", []),
                    str(latest["run_id"]),
                ]
                stored["source"] = latest["request"].get(
                    "source", latest["request"]["submission"]
                )

            row = await fetch_one(
                conn,
                insert(runs)
                .values(
                    run_id=uuid4(),
                    session_id=session_id,
                    action=body.action,
                    request=stored,
                    idempotency_key=body.idempotency_key,
                    status="pending",
                    created_at=func.clock_timestamp(),
                    updated_at=func.clock_timestamp(),
                )
                .returning(runs),
            )
            assert row is not None
            await self._event(conn, row, "run.pending", {})
            return row

    async def _event(
        self, conn: AsyncConnection, run: dict, kind: str, payload: object
    ):
        await conn.execute(
            insert(events).values(
                session_id=run["session_id"],
                run_id=run["run_id"],
                kind=kind,
                payload=public_data(payload),
            )
        )

    async def event(self, run: dict, kind: str, payload: object):
        async with self.engine.begin() as conn:
            row = await fetch_one(
                conn,
                select(runs).where(runs.c.run_id == run["run_id"]).with_for_update(),
            )
            if row and row["status"] == "running":
                await self._event(conn, row, kind, payload)

    async def transition(
        self, run_id: UUID, status: str, error: dict | None = None
    ) -> dict:
        async with self.engine.begin() as conn:
            row = await fetch_one(
                conn, select(runs).where(runs.c.run_id == run_id).with_for_update()
            )
            if row is None:
                raise RuntimeProblem("not_found", 404)
            if row["status"] not in ("pending", "running"):
                return row
            row = await fetch_one(
                conn,
                update(runs)
                .where(runs.c.run_id == run_id)
                .values(
                    status=status,
                    error=error if error else None,
                    updated_at=func.clock_timestamp(),
                )
                .returning(runs),
            )
            assert row is not None
            await self._event(
                conn, row, f"run.{status}", {"status": status, "error": error}
            )
            return row

    async def recover_abandoned(self):
        for row in await self._rows(
            select(runs.c.run_id).where(runs.c.status == "running")
        ):
            await self.transition(row["run_id"], "recovery_required")

    async def claim(self) -> dict | None:
        async with self.engine.begin() as conn:
            row = await fetch_one(
                conn,
                select(runs)
                .where(runs.c.status == "pending")
                .order_by(runs.c.created_at, runs.c.run_id)
                .limit(1)
                .with_for_update(skip_locked=True),
            )
            if row is not None:
                row = await fetch_one(
                    conn,
                    update(runs)
                    .where(runs.c.run_id == row["run_id"])
                    .values(status="running", updated_at=func.clock_timestamp())
                    .returning(runs),
                )
                assert row is not None
                await self._event(conn, row, "run.running", {"status": "running"})
            return row

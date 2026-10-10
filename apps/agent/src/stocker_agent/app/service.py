"""Graph execution and checkpoint queries, independent of HTTP transport."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from stocker_agent.app.errors import RuntimeProblem
from stocker_agent.app.models import (
    TERMINAL_STATUSES,
    Assistant,
    AssistantInput,
    CheckpointComparison,
    Run,
    RunInput,
    RuntimeEvent,
    Session,
    SessionInput,
    StateView,
)
from stocker_agent.app.repository import RuntimeRepository
from stocker_agent.app.serialization import public_data


def state_view(snapshot: StateSnapshot) -> StateView:
    values = public_data(snapshot.values)
    if not isinstance(values, dict):
        raise RuntimeProblem("unsupported_state_shape", 500)
    return StateView(
        values=values,
        next=list(snapshot.next),
        checkpoint_id=snapshot.config.get("configurable", {}).get("checkpoint_id"),
        created_at=snapshot.created_at,
        metadata=public_data(snapshot.metadata),
        interrupts=[
            public_data(item) for task in snapshot.tasks for item in task.interrupts
        ],
    )


class SessionService:
    def __init__(
        self, repository: RuntimeRepository, graphs: dict[str, CompiledStateGraph]
    ):
        self.repository = repository
        self.graphs = graphs

    async def graph(self, session_id: UUID):
        session = await self.repository.get_session(session_id)
        if session["graph_id"] not in self.graphs:
            raise RuntimeProblem("graph_unavailable", 409)
        config = {"configurable": {"thread_id": str(session_id)}, **session["config"]}
        return self.graphs[session["graph_id"]], config

    async def state(
        self, session_id: UUID, checkpoint_id: str | None = None
    ) -> StateView:
        graph, config = await self.graph(session_id)
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        snapshot = await graph.aget_state(config)
        if checkpoint_id and not snapshot.created_at:
            raise RuntimeProblem("checkpoint_not_found", 404)
        return state_view(snapshot)

    async def history(
        self, session_id: UUID, before: str | None, limit: int
    ) -> list[StateView]:
        graph, config = await self.graph(session_id)
        cursor = None
        if before:
            await self.state(session_id, before)
            cursor = {
                "configurable": {**config["configurable"], "checkpoint_id": before}
            }
        return [
            state_view(snapshot)
            async for snapshot in graph.aget_state_history(
                config, before=cursor, limit=limit
            )
        ]

    async def compare(
        self, session_id: UUID, left: str, right: str
    ) -> CheckpointComparison:
        a, b = await self.state(session_id, left), await self.state(session_id, right)
        return CheckpointComparison(
            left=a,
            right=b,
            changed_keys=sorted(
                key
                for key in a.values.keys() | b.values.keys()
                if a.values.get(key) != b.values.get(key)
            ),
        )

    def graph_ids(self) -> list[str]:
        return sorted(self.graphs)

    async def ready(self) -> None:
        await self.repository.ready()

    async def create_assistant(self, body: AssistantInput) -> Assistant:
        if body.graph_id not in self.graphs:
            raise RuntimeProblem("graph_not_found", 404)
        return Assistant.model_validate(await self.repository.assistant(body))

    async def assistants(self, after: UUID | None, limit: int) -> list[Assistant]:
        return [
            Assistant.model_validate(row)
            for row in await self.repository.list_assistants(after, limit)
        ]

    async def assistant(self, assistant_id: UUID) -> Assistant:
        return Assistant.model_validate(
            await self.repository.get_assistant(assistant_id)
        )

    async def create_session(self, body: SessionInput) -> Session:
        return Session.model_validate(await self.repository.session(body))

    async def sessions(self, after: UUID | None, limit: int) -> list[Session]:
        return [
            Session.model_validate(row)
            for row in await self.repository.list_sessions(after, limit)
        ]

    async def session(self, session_id: UUID) -> Session:
        return Session.model_validate(await self.repository.get_session(session_id))

    async def submit(self, session_id: UUID, body: RunInput) -> Run:
        await self.graph(session_id)
        return Run.model_validate(await self.repository.enqueue(session_id, body))

    async def runs(self, session_id: UUID, after: UUID | None, limit: int) -> list[Run]:
        await self.graph(session_id)
        return [
            Run.model_validate(row)
            for row in await self.repository.list_runs(session_id, after, limit)
        ]

    async def run(self, run_id: UUID) -> Run:
        return Run.model_validate(await self.repository.get_run(run_id))

    async def events(self, run_id: UUID, after: int, limit: int) -> list[RuntimeEvent]:
        await self.run(run_id)
        return [
            RuntimeEvent.model_validate(row)
            for row in await self.repository.run_events(run_id, after, limit)
        ]

    async def session_events(
        self, session_id: UUID, after: int, limit: int
    ) -> list[RuntimeEvent]:
        await self.graph(session_id)
        return [
            RuntimeEvent.model_validate(row)
            for row in await self.repository.session_events(session_id, after, limit)
        ]

    async def stream_events(
        self, run_id: UUID, after: int
    ) -> AsyncIterator[RuntimeEvent]:
        cursor = after
        while True:
            # Read status first so a terminal commit cannot hide its final event.
            run = await self.run(run_id)
            batch = await self.events(run_id, cursor, 200)
            for item in batch:
                cursor = item.event_id
                yield item
            if not batch and run.status in TERMINAL_STATUSES:
                return
            await asyncio.sleep(0.1)

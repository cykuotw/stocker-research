"""Durable graph execution worker, independent of HTTP dependencies."""

import asyncio
from time import monotonic
from uuid import UUID

from langgraph.types import Command

from stocker_agent.app.service import SessionService, state_view
from stocker_agent.config.errors import MissingModelSetting


class GraphRunner:
    """One worker per database, explicit replay after shutdown or execution failure."""

    def __init__(self, service: SessionService, poll_seconds: float):
        self.service = service
        self.repository = service.repository
        self.poll_seconds = poll_seconds
        self.active: tuple[UUID, asyncio.Task] | None = None
        self.worker: asyncio.Task | None = None
        self.stopping = False
        self.failure: str | None = None

    def start(self):
        self.worker = asyncio.create_task(self.work(), name="runtime-worker")

    async def stop(self):
        self.stopping = True
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass

    async def cancel(self, run_id: UUID):
        # Persist cancellation first so a claim racing this call cannot execute it.
        row = await self.repository.transition(run_id, "cancelled")
        if self.active and self.active[0] == run_id:
            self.active[1].cancel()
            try:
                await self.active[1]
            except asyncio.CancelledError:
                pass
        return row

    async def work(self):
        try:
            while True:
                run = await self.repository.claim()
                if not run:
                    await asyncio.sleep(self.poll_seconds)
                    continue
                task = asyncio.create_task(self.execute(run))
                self.active = (run["run_id"], task)
                try:
                    await task
                except asyncio.CancelledError:
                    if self.stopping:
                        await self.repository.transition(
                            run["run_id"], "recovery_required"
                        )
                        raise
                finally:
                    self.active = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — execution boundary isolates arbitrary graph failures
            # A broken database/worker must fail readiness instead of silently stopping.
            self.failure = type(exc).__name__

    async def execute(self, run: dict):
        try:
            current = await self.repository.get_run(run["run_id"])
            if current["status"] != "running":
                return
            graph, config = await self.service.graph(run["session_id"])
            config["configurable"]["runtime_run_id"] = str(run["run_id"])
            body = run["request"]["submission"]
            action = run["action"]
            if action == "resume":
                value = Command(resume=body["resume"])
            elif action == "recover":
                snapshot = await graph.aget_state(config)
                belongs_to_source = (snapshot.metadata or {}).get(
                    "runtime_run_id"
                ) in run["request"].get("source_run_ids", [])
                if snapshot.created_at and belongs_to_source:
                    if any(task.interrupts for task in snapshot.tasks):
                        await self.repository.transition(run["run_id"], "interrupted")
                        return
                    if not snapshot.next:
                        await self.repository.transition(run["run_id"], "completed")
                        return
                    value = None
                else:
                    source = run["request"]["source"]
                    if source.get("action", "input") == "resume":
                        value = Command(resume=source["resume"])
                    else:
                        value = source["input"]
            else:
                value = body["input"]
            starts: dict[str, float] = {}
            async for event in graph.astream_events(value, config, version="v2"):
                # Token fragments are transient; final model messages and graph updates persist.
                if event["event"] == "on_chat_model_stream" or (
                    event["event"] == "on_chain_stream" and event.get("parent_ids")
                ):
                    continue
                event_id = event["run_id"]
                duration = None
                if event["event"].endswith("_start"):
                    starts[event_id] = monotonic()
                elif event["event"].endswith("_end"):
                    began = starts.pop(event_id, None)
                    if began is not None:
                        duration = round((monotonic() - began) * 1000, 3)
                metadata = event.get("metadata", {})
                output = event.get("data", {}).get("output")
                event["inspection"] = {
                    "node": metadata.get("langgraph_node"),
                    "model": metadata.get("ls_model_name"),
                    "skill": metadata.get("skill_id"),
                    "tool": event["name"]
                    if event["event"].startswith("on_tool_")
                    else None,
                    "duration_ms": duration,
                    "usage": getattr(output, "usage_metadata", None),
                }
                await self.repository.event(run, event["event"], event)
            snapshot = await graph.aget_state(config)
            status = (
                "interrupted"
                if any(task.interrupts for task in snapshot.tasks)
                else "completed"
            )
            await self.repository.event(
                run,
                "state.updated",
                {
                    "checkpoint_id": state_view(snapshot).checkpoint_id,
                    "next": list(snapshot.next),
                    "interrupts": state_view(snapshot).interrupts,
                },
            )
            await self.repository.transition(run["run_id"], status)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — execution boundary isolates arbitrary graph failures
            error = {
                "code": "graph_execution_failed",
                "exception_type": type(exc).__name__,
            }
            if isinstance(exc, MissingModelSetting):
                error.update(code=exc.code, setting=exc.setting, message=exc.hint)
            await self.repository.transition(run["run_id"], "failed", error)

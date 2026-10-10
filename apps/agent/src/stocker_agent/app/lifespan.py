"""Compose web API, PostgreSQL, compiled graphs, and the execution lifecycle."""

import asyncio
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from psycopg import AsyncConnection, Error
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from stocker_agent.app.context import AppContext
from stocker_agent.app.errors import RuntimeProblem
from stocker_agent.app.repository import RuntimeRepository
from stocker_agent.app.runner import GraphRunner
from stocker_agent.app.service import SessionService
from stocker_agent.config.app import AppSettings

GraphFactory = Callable[[AsyncPostgresSaver], CompiledStateGraph]
LOCK_ID = 873_104_902_117


def echo_factory(saver: AsyncPostgresSaver) -> CompiledStateGraph:
    from stocker_agent.graphs.echo import build_echo_graph

    return build_echo_graph(checkpointer=saver)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    config: AppSettings,
    graph_factories: dict[str, GraphFactory] | None = None,
) -> AsyncGenerator[None]:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    conninfo = config.conninfo()
    kwargs: dict[str, Any] = {
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    }
    async with await AsyncConnection[dict[str, Any]].connect(
        conninfo, autocommit=True, row_factory=dict_row, prepare_threshold=0
    ) as owner:
        locked = await (
            await owner.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired", (LOCK_ID,)
            )
        ).fetchone()
        if not locked or not locked["acquired"]:
            raise RuntimeProblem("runtime_already_running", 503)
        async with AsyncConnectionPool[AsyncConnection[dict[str, Any]]](
            conninfo,
            kwargs=kwargs,
            min_size=1,
            max_size=config.max_pool_size,
            open=False,
        ) as pool:
            await pool.wait()
            repository = RuntimeRepository(pool)
            await repository.migrate()
            checkpoint_kwargs = {
                **kwargs,
                "options": "-c search_path=checkpoints,public",
            }
            async with AsyncConnectionPool[AsyncConnection[dict[str, Any]]](
                conninfo,
                kwargs=checkpoint_kwargs,
                min_size=1,
                max_size=config.max_pool_size,
                open=False,
            ) as checkpoint_pool:
                await checkpoint_pool.wait()
                saver = AsyncPostgresSaver(checkpoint_pool)
                await saver.setup()
                graphs = {
                    name: factory(saver)
                    for name, factory in (
                        graph_factories or {"echo": echo_factory}
                    ).items()
                }
                service = SessionService(repository, graphs)
                runner = GraphRunner(service, config.poll_seconds)
                await repository.recover_abandoned()
                runner.start()
                app.state.context = AppContext(
                    config, service, runner, owner.info.backend_pid
                )

                async def watch_ownership() -> None:
                    try:
                        while True:
                            await asyncio.sleep(0.2)
                            await owner.execute("SELECT 1")
                    except Error:
                        runner.failure = "ownership_connection_lost"
                        await runner.stop()

                ownership_watch = asyncio.create_task(watch_ownership())
                try:
                    yield
                finally:
                    app.state.context = None
                    ownership_watch.cancel()
                    try:
                        await ownership_watch
                    except asyncio.CancelledError:
                        pass
                    await runner.stop()

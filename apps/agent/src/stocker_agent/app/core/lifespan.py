"""Compose web API, PostgreSQL, compiled graphs, and the execution lifecycle."""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import Error

from stocker_agent.app.core.context import AppContext
from stocker_agent.app.database.factory import DatabaseFactory
from stocker_agent.app.repositories.runtime import RuntimeRepository
from stocker_agent.app.services.runner import GraphRunner
from stocker_agent.app.services.sessions import SessionService
from stocker_agent.config.app import AppSettings
from stocker_agent.graph_runtime.catalog import GRAPH_FACTORIES
from stocker_agent.graph_runtime.registry import GraphFactory, GraphRegistry
from stocker_agent.graph_runtime.resources import GraphResources, GraphResourcesFactory


@asynccontextmanager
async def lifespan(
    app: FastAPI,
    config: AppSettings,
    graph_factories: dict[str, GraphFactory] | None = None,
    graph_resources_factory: GraphResourcesFactory | None = None,
) -> AsyncGenerator[None]:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    async with DatabaseFactory().open(config) as database:
        repository = RuntimeRepository(database.engine)
        await repository.migrate()
        saver = AsyncPostgresSaver(database.checkpoint_pool)
        await saver.setup()
        resource_factory = graph_resources_factory or GraphResources.from_settings
        resources = resource_factory(saver)
        registry = GraphRegistry(
            GRAPH_FACTORIES if graph_factories is None else graph_factories
        )
        graphs = registry.build(resources)
        service = SessionService(repository, graphs)
        runner = GraphRunner(service, config.poll_seconds)
        await repository.recover_abandoned()
        runner.start()
        app.state.context = AppContext(
            config, service, runner, database.owner.info.backend_pid
        )

        async def watch_ownership() -> None:
            try:
                while True:
                    await asyncio.sleep(0.2)
                    await database.owner.execute("SELECT 1")
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

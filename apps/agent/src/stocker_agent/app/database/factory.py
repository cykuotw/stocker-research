"""Own one runtime engine, checkpoint pool and advisory lock per app lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from stocker_agent.app.core.errors import RuntimeProblem
from stocker_agent.config.app import AppSettings

LOCK_ID = 873_104_902_117


@dataclass(frozen=True)
class DatabaseResources:
    engine: AsyncEngine
    checkpoint_pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]]
    owner: AsyncConnection[dict[str, Any]]


class DatabaseFactory:
    @asynccontextmanager
    async def open(self, settings: AppSettings) -> AsyncGenerator[DatabaseResources]:
        conninfo = settings.conninfo()
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

            async def connect_runtime():
                return await AsyncConnection.connect(conninfo)

            engine = create_async_engine(
                "postgresql+psycopg://",
                async_creator=connect_runtime,
                pool_size=settings.max_pool_size,
                max_overflow=0,
                pool_pre_ping=True,
                hide_parameters=True,
            )
            try:
                async with AsyncConnectionPool[AsyncConnection[dict[str, Any]]](
                    conninfo,
                    kwargs={
                        "autocommit": True,
                        "row_factory": dict_row,
                        "prepare_threshold": 0,
                        "options": "-c search_path=checkpoints,public",
                    },
                    min_size=1,
                    max_size=settings.max_pool_size,
                    open=False,
                ) as checkpoint_pool:
                    await checkpoint_pool.wait()
                    yield DatabaseResources(engine, checkpoint_pool, owner)
            finally:
                await engine.dispose()

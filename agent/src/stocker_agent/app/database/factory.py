"""Own one runtime engine, checkpoint pool and advisory lock per app lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from math import ceil
from typing import Any

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
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
        options = (
            f"{conninfo_to_dict(conninfo).get('options', '')} "
            f"-c statement_timeout={ceil(settings.statement_timeout_seconds * 1000)} "
            f"-c lock_timeout={ceil(settings.lock_timeout_seconds * 1000)}"
        ).strip()
        async with await AsyncConnection[dict[str, Any]].connect(
            conninfo,
            autocommit=True,
            row_factory=dict_row,
            prepare_threshold=0,
            options=options,
        ) as owner:
            locked = await (
                await owner.execute(
                    "SELECT pg_try_advisory_lock(%s) AS acquired", (LOCK_ID,)
                )
            ).fetchone()
            if not locked or not locked["acquired"]:
                raise RuntimeProblem("runtime_already_running", 503)

            async def connect_runtime():
                return await AsyncConnection.connect(conninfo, options=options)

            engine = create_async_engine(
                "postgresql+psycopg://",
                async_creator=connect_runtime,
                pool_size=settings.runtime_pool_size,
                pool_timeout=settings.pool_timeout_seconds,
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
                        "options": f"{options} -c search_path=checkpoints,public",
                    },
                    min_size=1,
                    max_size=settings.checkpoint_pool_size,
                    timeout=settings.pool_timeout_seconds,
                    open=False,
                ) as checkpoint_pool:
                    await checkpoint_pool.wait(timeout=settings.pool_timeout_seconds)
                    yield DatabaseResources(engine, checkpoint_pool, owner)
            finally:
                await engine.dispose()

"""Own a bounded PostgreSQL pool for one Knowledge application lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from math import ceil
from typing import Any

from psycopg import AsyncConnection, Error
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from knowledge.config.database import DatabaseSettings


@dataclass(frozen=True)
class DatabaseResources:
    pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]]

    async def ready(self) -> None:
        async with self.pool.connection() as connection:
            await connection.execute("SELECT 1")


class DatabaseFactory:
    @asynccontextmanager
    async def open(
        self, settings: DatabaseSettings
    ) -> AsyncGenerator[DatabaseResources]:
        conninfo = settings.conninfo()
        options = (
            f"{conninfo_to_dict(conninfo).get('options', '')} "
            f"-c statement_timeout={ceil(settings.statement_timeout_seconds * 1000)} "
            f"-c lock_timeout={ceil(settings.lock_timeout_seconds * 1000)} "
            "-c search_path=pg_catalog,public"
        ).strip()
        pool = AsyncConnectionPool[AsyncConnection[dict[str, Any]]](
            conninfo,
            kwargs={"row_factory": dict_row, "options": options},
            min_size=1,
            max_size=settings.pool_size,
            timeout=settings.pool_timeout_seconds,
            open=False,
        )
        try:
            try:
                await pool.open(wait=True, timeout=settings.pool_timeout_seconds)
                resources = DatabaseResources(pool)
                await resources.ready()
            except Error, PoolTimeout:
                raise RuntimeError("Knowledge database startup failed") from None
            yield resources
        finally:
            await pool.close()

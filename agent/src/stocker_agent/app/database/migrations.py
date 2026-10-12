"""Apply immutable runtime SQL through the engine's psycopg driver transaction."""

from hashlib import sha256
from pathlib import Path
from typing import LiteralString, cast

from psycopg import AsyncConnection as PsycopgConnection
from psycopg.sql import SQL
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from stocker_agent.app.core.errors import RuntimeProblem
from stocker_agent.app.database.tables import schema_migrations


async def migrate_runtime(conn: AsyncConnection) -> None:
    sql = (Path(__file__).parents[1] / "migrations/001_runtime.sql").read_text()
    checksum = sha256(sql.encode()).hexdigest()
    # Only the trusted bundled DDL uses a driver call. No request data is SQL text.
    raw = await conn.get_raw_connection()
    driver = raw.driver_connection
    if not isinstance(driver, PsycopgConnection):
        raise TypeError("Runtime migrations require the psycopg driver")
    await driver.execute(SQL(cast(LiteralString, sql)), prepare=False)
    row = (
        await conn.execute(
            select(schema_migrations.c.checksum).where(schema_migrations.c.version == 1)
        )
    ).first()
    if row and row.checksum != checksum:
        raise RuntimeProblem("migration_checksum_mismatch", 500)
    await conn.execute(
        insert(schema_migrations)
        .values(version=1, checksum=checksum)
        .on_conflict_do_nothing()
    )

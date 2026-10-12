"""Bootstrap LangGraph tables with a separate migration statement timeout."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from stocker_agent.app.database.factory import DatabaseResources
from stocker_agent.config.app import AppSettings


async def setup_checkpoints(
    database: DatabaseResources, settings: AppSettings
) -> AsyncPostgresSaver:
    # LangGraph migrations may use CREATE INDEX CONCURRENTLY: keep autocommit.
    async with database.checkpoint_pool.connection() as connection:
        await connection.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (f"{settings.migration_timeout_seconds}s",),
        )
        try:
            await AsyncPostgresSaver(connection).setup()
        finally:
            await connection.execute(
                "SELECT set_config('statement_timeout', %s, false)",
                (f"{settings.statement_timeout_seconds}s",),
            )
    return AsyncPostgresSaver(database.checkpoint_pool)

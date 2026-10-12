"""Timeout configuration, migration restoration, and live transaction recovery."""

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.errors import LockNotAvailable, QueryCanceled
from psycopg_pool import PoolTimeout
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeout

from stocker_agent.app.database import checkpoints
from stocker_agent.app.database.factory import DatabaseFactory
from stocker_agent.app.repositories.runtime import RuntimeRepository
from stocker_agent.config.app import AppSettings


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.asyncio
async def test_checkpoint_migration_restores_timeout(monkeypatch, failure):
    config = AppSettings(database_uri="postgresql://localhost/stocker_agent_runtime")
    connection = Mock(execute=AsyncMock())

    @asynccontextmanager
    async def acquire():
        yield connection

    database = SimpleNamespace(checkpoint_pool=Mock(connection=acquire))
    bootstrap = Mock(
        setup=AsyncMock(side_effect=RuntimeError("migration") if failure else None)
    )
    saver = Mock()
    monkeypatch.setattr(
        checkpoints, "AsyncPostgresSaver", Mock(side_effect=[bootstrap, saver])
    )
    if failure:
        with pytest.raises(RuntimeError, match="migration"):
            await checkpoints.setup_checkpoints(database, config)
    else:
        assert await checkpoints.setup_checkpoints(database, config) is saver
    assert [call.args[1] for call in connection.execute.await_args_list] == [
        (f"{config.migration_timeout_seconds}s",),
        (f"{config.statement_timeout_seconds}s",),
    ]


@pytest.mark.parametrize(
    "name",
    [
        "runtime_pool_size",
        "checkpoint_pool_size",
        "connect_timeout_seconds",
        "pool_timeout_seconds",
        "statement_timeout_seconds",
        "lock_timeout_seconds",
        "migration_timeout_seconds",
        "shutdown_timeout_seconds",
    ],
)
def test_database_limits_reject_zero(name):
    with pytest.raises(ValidationError):
        AppSettings(**{name: 0})


def test_connection_timeout_overrides_uri_and_environment(monkeypatch):
    monkeypatch.setenv("APP_CONNECT_TIMEOUT_SECONDS", "7")
    config = AppSettings(
        database_uri="postgresql://localhost/stocker_agent_runtime?connect_timeout=90"
    )
    assert conninfo_to_dict(config.conninfo())["connect_timeout"] == "7"


@pytest.fixture
def live_settings():
    uri = os.environ.get("TEST_RUNTIME_DATABASE_URI")
    if not uri:
        pytest.skip("Set TEST_RUNTIME_DATABASE_URI for PostgreSQL integration")
    return AppSettings(
        database_uri=uri,
        runtime_pool_size=1,
        checkpoint_pool_size=1,
        statement_timeout_seconds=0.05,
        lock_timeout_seconds=0.02,
        pool_timeout_seconds=0.05,
    )


@pytest.mark.asyncio
async def test_runtime_timeout_rolls_back_and_connection_remains_usable(live_settings):
    # Startup needs a less aggressive acquisition deadline than the exhaustion check.
    config = live_settings.model_copy(update={"pool_timeout_seconds": 2})
    async with DatabaseFactory().open(config) as database:
        await RuntimeRepository(database.engine).migrate(
            config.migration_timeout_seconds
        )
        with pytest.raises(DBAPIError) as caught:
            async with database.engine.begin() as conn:
                await conn.execute(text("SELECT pg_sleep(0.2)"))
        assert isinstance(caught.value.orig, QueryCanceled)
        async with database.engine.begin() as conn:
            assert (
                await conn.execute(text("SHOW statement_timeout"))
            ).scalar_one() == "50ms"
            assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1
        # Short lock wait wins over the statement timeout, and rolls back normally.
        async with database.owner.transaction():
            await database.owner.execute(
                "LOCK TABLE runtime.assistants IN ACCESS EXCLUSIVE MODE"
            )
            with pytest.raises(DBAPIError) as caught:
                async with database.engine.begin() as conn:
                    await conn.execute(text("SELECT * FROM runtime.assistants"))
            assert isinstance(caught.value.orig, LockNotAvailable)


@pytest.mark.asyncio
async def test_checkpoint_timeout_restored_after_real_setup(live_settings):
    config = live_settings.model_copy(update={"pool_timeout_seconds": 2})
    async with DatabaseFactory().open(config) as database:
        await RuntimeRepository(database.engine).migrate(
            config.migration_timeout_seconds
        )
        await checkpoints.setup_checkpoints(database, config)
        async with database.checkpoint_pool.connection() as conn:
            assert (await (await conn.execute("SHOW statement_timeout")).fetchone())[
                "statement_timeout"
            ] == "50ms"
            with pytest.raises(QueryCanceled):
                await conn.execute("SELECT pg_sleep(0.2)")
            assert (await (await conn.execute("SELECT 1 AS value")).fetchone())[
                "value"
            ] == 1


@pytest.mark.asyncio
async def test_exhausted_pools_fail_at_acquisition_deadline(live_settings):
    # Give initial pool startup enough time; acquisition remains explicitly bounded.
    config = live_settings.model_copy(update={"pool_timeout_seconds": 0.5})
    async with DatabaseFactory().open(config) as database:
        async with database.engine.connect():
            with pytest.raises(SQLAlchemyTimeout):
                async with database.engine.connect():
                    pytest.fail("runtime pool must not overflow")
        async with database.checkpoint_pool.connection():
            with pytest.raises(PoolTimeout):
                async with database.checkpoint_pool.connection(timeout=0.05):
                    pytest.fail("checkpoint pool must not overflow")

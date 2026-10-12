"""Pool lifecycle, bounded connections, and cleanup on failures."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import PoolTimeout

from knowledge.app.database.factory import DatabaseFactory, DatabaseResources
from knowledge.config.database import DatabaseSettings


@pytest.mark.asyncio
async def test_pool_limits_timeouts_and_close():
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.close = AsyncMock()
    settings = DatabaseSettings(password="fixture-secret", pool_size=2)
    with (
        patch(
            "knowledge.app.database.factory.AsyncConnectionPool", return_value=pool
        ) as constructor,
        patch.object(DatabaseResources, "ready", new_callable=AsyncMock) as ready,
    ):
        # Generic subscription returns the same mock constructor.
        constructor.__class_getitem__ = MagicMock(return_value=constructor)
        constructor.__getitem__.return_value = constructor
        async with DatabaseFactory().open(settings) as resources:
            assert resources.pool is pool
            ready.assert_awaited_once()
        kwargs = constructor.call_args.kwargs
        assert kwargs["max_size"] == 2
        assert kwargs["min_size"] == 1
        assert kwargs["open"] is False
        assert "statement_timeout=30000" in kwargs["kwargs"]["options"]
        assert "lock_timeout=5000" in kwargs["kwargs"]["options"]
        assert (
            conninfo_to_dict(constructor.call_args.args[0])["dbname"]
            == "stocker_knowledge"
        )
        pool.open.assert_awaited_once_with(wait=True, timeout=5)
        pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_failure_closes_pool_and_hides_details():
    pool = MagicMock()
    pool.open = AsyncMock(side_effect=PoolTimeout("fixture-secret"))
    pool.close = AsyncMock()
    with patch(
        "knowledge.app.database.factory.AsyncConnectionPool", return_value=pool
    ) as constructor:
        constructor.__getitem__.return_value = constructor
        with pytest.raises(RuntimeError, match="^Knowledge database startup failed$"):
            async with DatabaseFactory().open(
                DatabaseSettings(password="fixture-secret")
            ):
                pytest.fail("Startup must fail")
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_application_failure_still_closes_pool():
    pool = MagicMock()
    pool.open = AsyncMock()
    pool.close = AsyncMock()
    with (
        patch(
            "knowledge.app.database.factory.AsyncConnectionPool", return_value=pool
        ) as constructor,
        patch.object(DatabaseResources, "ready", new_callable=AsyncMock),
    ):
        constructor.__getitem__.return_value = constructor
        with pytest.raises(ValueError, match="application error"):
            async with DatabaseFactory().open(
                DatabaseSettings(password="fixture-secret")
            ):
                raise ValueError("application error")
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_readiness_borrows_a_connection():
    connection = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = context
    await DatabaseResources(pool).ready()
    connection.execute.assert_awaited_once_with("SELECT 1")
    context.__aexit__.assert_awaited_once()

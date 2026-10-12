"""Database cleanup and parameterization checks without external resources."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import dialect

from stocker_agent.app.database import factory as module
from stocker_agent.app.database.tables import assistants
from stocker_agent.config.app import AppSettings


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_open", [False, True])
async def test_factory_closes_pool_engine_owner_in_order(monkeypatch, fail_open):
    order = []
    owner = Mock(
        execute=AsyncMock(
            return_value=Mock(fetchone=AsyncMock(return_value={"acquired": True}))
        )
    )

    @asynccontextmanager
    async def owner_context():
        try:
            yield owner
        finally:
            order.append("owner")

    connection = MagicMock()
    connection.__getitem__ = Mock(return_value=connection)
    connection.connect = AsyncMock(return_value=owner_context())
    monkeypatch.setattr(module, "AsyncConnection", connection)
    engine = Mock(dispose=AsyncMock(side_effect=lambda: order.append("engine")))
    create_engine = Mock(return_value=engine)
    monkeypatch.setattr(module, "create_async_engine", create_engine)

    class Pool:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, *args, **kwargs):
            assert kwargs["max_size"] == 3
            assert kwargs["timeout"] == 0.5
            assert "statement_timeout=2000" in kwargs["kwargs"]["options"]
            assert "lock_timeout=100" in kwargs["kwargs"]["options"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            order.append("pool")

        async def wait(self, timeout):
            assert timeout == 0.5
            if fail_open:
                raise RuntimeError("fixture startup failure")

    monkeypatch.setattr(module, "AsyncConnectionPool", Pool)
    settings = AppSettings(
        database_uri="postgresql://localhost/stocker_research",
        runtime_pool_size=2,
        checkpoint_pool_size=3,
        pool_timeout_seconds=0.5,
        statement_timeout_seconds=2,
        lock_timeout_seconds=0.1,
    )
    if fail_open:
        with pytest.raises(RuntimeError, match="fixture startup"):
            async with module.DatabaseFactory().open(settings):
                pytest.fail("failed initialization must not yield resources")
    else:
        async with module.DatabaseFactory().open(settings) as resources:
            assert resources.engine is engine
            assert resources.owner is owner
    assert order == ["pool", "engine", "owner"]
    assert create_engine.call_args.kwargs["hide_parameters"] is True
    assert create_engine.call_args.kwargs["max_overflow"] == 0
    assert create_engine.call_args.kwargs["pool_size"] == 2
    assert create_engine.call_args.kwargs["pool_timeout"] == 0.5


def test_sqlalchemy_keeps_sql_like_input_in_bound_parameters():
    malicious = "'); DROP SCHEMA runtime CASCADE; --"
    statement = insert(assistants).values(
        assistant_id=uuid4(),
        graph_id="echo",
        name=malicious,
        config={"text": malicious},
    )
    compiled = statement.compile(dialect=dialect())
    assert malicious not in str(compiled)
    assert compiled.params["name"] == malicious
    assert compiled.params["config"] == {"text": malicious}

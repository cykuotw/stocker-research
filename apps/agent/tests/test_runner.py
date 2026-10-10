"""Worker cancellation must propagate without being persisted as a failure."""

import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from stocker_agent.app.services.runner import GraphRunner


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["work", "execute"])
async def test_cancellation_bypasses_failure_handlers(operation):
    repository = Mock(
        claim=AsyncMock(side_effect=asyncio.CancelledError),
        get_run=AsyncMock(side_effect=asyncio.CancelledError),
        transition=AsyncMock(),
    )
    runner = GraphRunner(Mock(repository=repository), 0.1)
    with pytest.raises(asyncio.CancelledError):
        if operation == "work":
            await runner.work()
        else:
            await runner.execute({"run_id": uuid4()})
    assert runner.failure is None
    repository.transition.assert_not_awaited()

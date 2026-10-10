"""Graph runner dependency."""

from typing import Annotated

from fastapi import Depends

from stocker_agent.app.dependencies.context import Context
from stocker_agent.app.services.runner import GraphRunner


async def get_runner(context: Context) -> GraphRunner:
    return context.runner


Runner = Annotated[GraphRunner, Depends(get_runner)]

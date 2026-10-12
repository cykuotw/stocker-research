"""Session service dependency."""

from typing import Annotated

from fastapi import Depends

from stocker_agent.app.dependencies.context import Context
from stocker_agent.app.services.sessions import SessionService


async def get_service(context: Context) -> SessionService:
    return context.service


Service = Annotated[SessionService, Depends(get_service)]

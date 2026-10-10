"""Application context dependency."""

from typing import Annotated

from fastapi import Depends, Request

from stocker_agent.app.core.context import AppContext
from stocker_agent.app.core.errors import RuntimeProblem


def get_context(request: Request) -> AppContext:
    context = getattr(request.app.state, "context", None)
    if not isinstance(context, AppContext):
        raise RuntimeProblem("runtime_unavailable", 503)
    return context


Context = Annotated[AppContext, Depends(get_context)]

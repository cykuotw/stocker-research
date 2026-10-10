"""Application-scoped resources constructed and released by lifespan."""

from dataclasses import dataclass, field

from stocker_agent.app.services.runner import GraphRunner
from stocker_agent.app.services.sessions import SessionService
from stocker_agent.config.app import AppSettings


@dataclass(frozen=True, slots=True)
class AppContext:
    settings: AppSettings = field(repr=False)
    service: SessionService
    runner: GraphRunner
    ownership_pid: int

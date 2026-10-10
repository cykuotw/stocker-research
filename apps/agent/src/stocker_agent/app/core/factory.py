"""Compose configuration, transport, and application lifecycle."""

from functools import partial
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import Lifespan

from stocker_agent.app.core.errors import RuntimeProblem
from stocker_agent.app.core.lifespan import lifespan as runtime_lifespan
from stocker_agent.app.routers import inspection, runs, sessions, system
from stocker_agent.config.app import AppSettings
from stocker_agent.graph_runtime.registry import GraphFactory
from stocker_agent.graph_runtime.resources import GraphResourcesFactory


def configure_static(app: FastAPI, directory: Path | None) -> None:
    if directory and (directory / "index.html").is_file():

        @app.api_route("/api", methods=["GET", "POST", "HEAD"], include_in_schema=False)
        @app.api_route(
            "/api/{path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            include_in_schema=False,
        )
        async def unknown_api(path: str = "") -> None:
            raise RuntimeProblem("not_found", 404)

        app.frontend("/", directory=directory, fallback="index.html")


def create_app(
    settings: AppSettings | None = None,
    graph_factories: dict[str, GraphFactory] | None = None,
    *,
    lifespan: Lifespan[FastAPI] | None = None,
    graph_resources_factory: GraphResourcesFactory | None = None,
) -> FastAPI:
    config = settings if settings is not None else AppSettings()
    lifecycle = (
        lifespan
        if lifespan is not None
        else partial(
            runtime_lifespan,
            config=config,
            graph_factories=graph_factories,
            graph_resources_factory=graph_resources_factory,
        )
    )
    app = FastAPI(title="Stocker Agent Runtime", version="0.1.0", lifespan=lifecycle)
    app.state.context = None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @app.exception_handler(RuntimeProblem)
    async def problem_handler(request: Request, exc: RuntimeProblem) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": {"code": exc.code}}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "fields": [list(item["loc"]) for item in exc.errors()],
                }
            },
        )

    for router in (system.router, sessions.router, runs.router, inspection.router):
        app.include_router(router)
    configure_static(app, config.static_directory)
    return app

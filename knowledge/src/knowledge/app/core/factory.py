"""Standalone service assembly; no chat runtime or external resource startup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knowledge.app.routers import system
from knowledge.config.app import AppSettings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    config = settings if settings is not None else AppSettings()
    app = FastAPI(title="Stocker Knowledge Service", version="0.1.0")
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["GET"],
            allow_headers=["Content-Type"],
        )
    app.include_router(system.router)
    return app

"""Standalone HTTP assembly with service-owned database resources."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knowledge.app.database.factory import DatabaseFactory
from knowledge.app.routers import system
from knowledge.config.app import AppSettings
from knowledge.config.database import DatabaseSettings


def create_app(
    settings: AppSettings | None = None,
    database_settings: DatabaseSettings | None = None,
    database_factory: DatabaseFactory | None = None,
) -> FastAPI:
    config = settings if settings is not None else AppSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        db_config = (
            database_settings if database_settings is not None else DatabaseSettings()
        )
        factory = (
            database_factory if database_factory is not None else DatabaseFactory()
        )
        app.state.database = None
        async with factory.open(db_config) as database:
            app.state.database = database
            try:
                yield
            finally:
                app.state.database = None

    app = FastAPI(title="Stocker Knowledge Service", version="0.1.0", lifespan=lifespan)
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["GET"],
            allow_headers=["Content-Type"],
        )
    app.include_router(system.router)
    return app

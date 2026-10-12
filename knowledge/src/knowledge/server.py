"""FastAPI entrypoint for the Stocker Knowledge Service."""

from knowledge.app.core.factory import create_app

app = create_app()

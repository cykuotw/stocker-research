"""Backend entrypoint; application assembly and resources live in app/."""

from stocker_agent.app.factory import create_app

app = create_app()

# Stocker Agent

Python backend for Taiwan equity research. Currently a package scaffold; graph
workflows and data integrations are planned.

From the repository root, run `make run` or `make ruff`.
Use `uv sync --project apps/agent --locked` to install Python dependencies.

Keep future application code under `src/stocker_agent/`. A graph and local
`langgraph.json` are required before `make dev` can start Agent Server.

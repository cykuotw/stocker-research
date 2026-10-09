# Stocker Agent

Python backend for Taiwan equity research. Includes a model-free echo graph for
local testing; research workflows and data integrations are planned.

From the repository root, run `make dev` or `make ruff`.
Use `uv sync --project apps/agent --locked` to install Python dependencies.

Run `make dev` to start Agent Server at `http://localhost:2024` with graph ID
`echo`. Send a chat message through Studio to receive `Echo: <your message>`.
No API key is required. Keep application code under `src/stocker_agent/`.

# Stocker Research

Research workflows and document knowledge services for Stocker’s Taiwan equity
research platform. Quantitative data collection remains in the separate Stocker
project. Automated trading is outside the initial scope.

## Layout and service boundaries

```text
agent/       FastAPI + LangGraph research runtime; Python package stocker_agent
knowledge/   Independent FastAPI knowledge service; Python package knowledge
studio/      React + Vite Agent runtime and inspection UI
dashboard/   Reserved for the Knowledge document and retrieval management UI
chat/        Reserved for the user-facing chat bubble and conversation panel
docs/        Architecture and operator documentation
Makefile     Development commands for both backends and Agent Studio
```

Agent owns research methods, sessions, runs, checkpoints, synthesis, and research
artifacts. Knowledge owns document ingestion, extraction, provenance, and retrieval.
They keep independent manifests, lockfiles, settings, tests, and deployments.
Agent integration through Knowledge’s public API/MCP contracts is planned.

The Agent runtime and skill-driven echo graph are implemented. Agent Studio
supports sessions, chat, execution inspection, state, and checkpoints. Research
workflows and external data integrations remain planned.

Knowledge provides `/health`, `/info`, and lazy model-provider adapters.
Ingestion, extraction, persistence, retrieval, and MCP are planned. Its dashboard
is a documentation placeholder, separate from Agent Studio.
The standalone Chat bubble is also a documentation placeholder.

## Development

Requires Python 3.14+, `uv`, and `make`. Agent also requires PostgreSQL configuration;
Knowledge’s current foundation starts without database or model credentials.
Studio requires Node.js 22.12+ and pnpm 12.10.1.

From the repository root:

```bash
uv sync --project agent --locked
uv sync --project knowledge --locked
make dev-agent       # http://127.0.0.1:8000; make dev is an alias
make dev-knowledge   # http://127.0.0.1:8001; run in another terminal
make ruff
make test            # both backend suites
```

For Agent Studio:

```bash
pnpm --dir studio install --frozen-lockfile
make studio          # hot reload at http://127.0.0.1:5173
```

You can also run `pnpm --dir studio run dev` directly.
Each UI owns its dependencies; there is no root pnpm workspace or shared UI package.

See [Agent setup](agent/README.md), [Studio setup](studio/README.md),
[Knowledge setup](knowledge/README.md), and
[Knowledge architecture](docs/knowledge/architecture.md).

## Component documentation

| Component | Setup and backend integration | Architecture |
| --- | --- | --- |
| Agent | [Backend](docs/agent/backend.md), [README](agent/README.md) | [Architecture](docs/agent/architecture.md) |
| Knowledge | [Backend](docs/knowledge/backend.md), [README](knowledge/README.md) | [Architecture](docs/knowledge/architecture.md) |
| Studio | [Backend integration](docs/studio/backend.md), [README](studio/README.md) | [Architecture](docs/studio/architecture.md) |
| Dashboard | [Backend integration](docs/dashboard/backend.md), [README](dashboard/README.md) | [Target architecture](docs/dashboard/architecture.md) |
| Chat | [Backend integration](docs/chat/backend.md), [README](chat/README.md) | [Target architecture](docs/chat/architecture.md) |

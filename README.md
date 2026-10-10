# Stocker

An AI research assistant for Taiwan equities, with company research and
cyclical-bottom analysis as its initial focus. Research workflows and data
integrations are planned; the backend includes a skill-driven echo graph for local testing.
Automated trading is outside the initial scope.

## Layout

```text
apps/
  agent/    Python backend using LangGraph and LangChain
  studio/   Agent Chat UI for development and debugging
  web/      Reserved for the production frontend
packages/   Reserved for shared frontend packages
```

The planned backend uses Gemini, structured financial data, and traceable
research evidence. Studio provides a React + Vite development UI for sessions, chat, execution
events, observed traces, state, and checkpoint inspection.

## Development

Requires Python 3.14+, `uv`, Node.js 22+, pnpm 12.10.1, and `make`.
Run commands from the repository root:

```bash
uv sync --project apps/agent --locked
pnpm --dir apps/studio install --frozen-lockfile
make ruff
make ruff-fix # Apply automatic lint fixes and formatting
make studio
```

`make studio` builds Studio and previews static assets at
`http://127.0.0.1:3000`. For hot reload, run `pnpm --dir apps/studio dev`
at `http://127.0.0.1:5173`.

`make dev` starts the custom FastAPI + PostgreSQL backend on port 8000. See
[local runtime setup](apps/agent/README.md) for configuration, API endpoints,
and persistence. No LangSmith account, license, or Agent Server is needed.
Studio connects to the custom runtime through its Service URL field. Select a
graph and session to chat and inspect execution. API documentation remains
available at `http://127.0.0.1:8000/docs`.

Frontend checks and build:

```bash
pnpm --dir apps/studio lint
pnpm --dir apps/studio build
```

See [backend notes](apps/agent/README.md) and [Studio notes](apps/studio/README.md).

Each frontend manages its own package manifest, pnpm lockfile, and dependencies.
There is no root pnpm workspace; `apps/web/` remains a placeholder.

# Stocker

An AI research assistant for Taiwan equities, with company research and
cyclical-bottom analysis as its initial focus. Research workflows and data
integrations are planned; the backend currently runs a package scaffold.
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
research evidence. The Studio currently provides the upstream chat interface;
custom graph and state inspection panels have not been added.

## Development

Requires Python 3.14+, `uv`, Node.js 22+, pnpm 12.10.1, and `make`.
Run commands from the repository root:

```bash
uv sync --project apps/agent --locked
pnpm install --frozen-lockfile
make run
make ruff
make studio
```

`make run` prints the backend scaffold greeting. `make studio` starts the chat UI.
Connect it to a running LangGraph server using the URL and graph ID in its setup
screen. The UI needs a graph that supports chat messages.

`make dev` starts the LangGraph development server from `apps/agent`, once a graph
and `apps/agent/langgraph.json` have been implemented. Neither exists yet.

Frontend checks and build:

```bash
pnpm lint:studio
pnpm build:studio
```

See [backend notes](apps/agent/README.md) and [Studio notes](apps/studio/README.md).

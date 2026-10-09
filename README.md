# Stocker

An AI research assistant for Taiwan equities, with company research and
cyclical-bottom analysis as its initial focus. Research workflows and data
integrations are planned; the backend includes a model-free echo graph for local testing.
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
make ruff
make studio
```

`make studio` starts the chat UI.
Connect it to a running LangGraph server using the URL and graph ID in its setup
screen. The UI needs a graph that supports chat messages.

For a local sanity test, run `make dev` and `make studio` in separate terminals.
Open the Agent Chat UI at `http://localhost:3000` (or the Local URL printed by
Next.js if that port is busy). `make dev` runs the backend without opening
LangSmith Studio.
In the UI setup screen, enter `http://localhost:2024` as the server URL and `echo`
as the graph ID. Leave the API key empty. Sending `hello` returns `Echo: hello`.
If an existing browser URL contains `assistantId=agent`, change it to
`assistantId=echo` or reopen the setup screen without query parameters.
The echo graph requires no model credentials and replies in one step, without
token-by-token generation.

Frontend checks and build:

```bash
pnpm lint:studio
pnpm build:studio
```

See [backend notes](apps/agent/README.md) and [Studio notes](apps/studio/README.md).

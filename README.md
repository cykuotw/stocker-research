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
research evidence. The Studio currently provides the upstream chat interface;
custom graph and state inspection panels have not been added.

## Development

Requires Python 3.14+, `uv`, Node.js 22+, pnpm 12.10.1, and `make`.
Run commands from the repository root:

```bash
uv sync --project apps/agent --locked
pnpm --dir apps/studio install --frozen-lockfile
make ruff
make studio
```

`make studio` builds the chat UI, then starts the production server locally.
It rebuilds on each invocation and does not provide hot reload. For UI development,
run `pnpm --dir apps/studio dev` instead.
Connect it to a running LangGraph server using the URL and graph ID in its setup
screen. The UI needs a graph that supports chat messages.

For a local sanity test, run `make dev` and `make studio` in separate terminals.
Open the Agent Chat UI at `http://localhost:3000`; ensure the port is available.
`make dev` runs the backend without opening
LangSmith Studio.
In the UI setup screen, enter `http://localhost:2024` as the server URL and `echo`
as the graph ID. Leave the API key empty. Sending `hello` returns `Echo: hello`.
If an existing browser URL contains `assistantId=agent`, change it to
`assistantId=echo` or reopen the setup screen without query parameters.
The echo graph loads the `echo-agent` skill and uses its configured model tier.
Set `GOOGLE_API_KEY` in `apps/agent/.env` or the backend process environment.
The shared config layer automatically loads `.env` and `settings.toml`. The model calls `print_user_message` to print the
greeting in the backend console, then replies with `Echo: <your message>`.
The API key field in Studio is for server authentication, not the Gemini key.

Frontend checks and build:

```bash
pnpm --dir apps/studio lint
pnpm --dir apps/studio build
```

See [backend notes](apps/agent/README.md) and [Studio notes](apps/studio/README.md).

Each frontend manages its own package manifest, pnpm lockfile, and dependencies.
There is no root pnpm workspace; `apps/web/` remains a placeholder.

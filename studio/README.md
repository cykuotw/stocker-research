# Stocker Studio

React + Vite development UI for the custom FastAPI/LangGraph runtime.
The session, conversation, and inspector layout follows the debugging flow of
[ADK Web](https://github.com/google/adk-web/discussions/59), using LangGraph
runs, execution events, checkpoints, and interrupts.

## Run locally

Requires Node.js 22.12+ and pnpm 12.10.1. From the repository root:

```bash
pnpm --dir studio install --frozen-lockfile
make dev
```

In another terminal:

```bash
make studio
```

`make studio` starts the Vite development server with hot reload at
`http://127.0.0.1:5173`. You can also use `pnpm --dir studio run dev`, or
`pnpm run dev` from `studio/`. The UI defaults to the API at
`http://127.0.0.1:8000`.
The frontend has no Node application server, Next.js, or Agent Server proxy.

## Debug a graph

Select a graph and an assistant configuration, then create or select a session.
Send messages, inspect run status, and cancel an active run. Interrupted runs
accept a JSON or text resume value. Failed, cancelled, or interrupted-by-shutdown
work requires an explicit acknowledgement before recovery can replay nodes.

The inspector provides:

- Run history and persisted execution events, with filtering and payload details.
- An observed execution hierarchy derived from LangGraph event parent IDs.
- Recorded event input/output and node, model, skill, tool, duration, and usage
  metadata when available.
- Current checkpoint state, read-only checkpoint history, and comparison.

Conversation content comes from LangGraph checkpoints. Events update over SSE,
with reconnect cursors and duplicate suppression. Final saved messages appear as
checkpoints advance; individual token streaming is not implemented. The Trace
view shows observed spans, rather than the full graph definition or an external
tracing service. Uploaded attachments, editable checkpoint branches, and a
research-artifact viewer are not implemented.

See [backend integration](../docs/studio/backend.md) and
[Studio architecture](../docs/studio/architecture.md). The standalone user-facing
Chat bubble is [planned separately](../chat/README.md).

## Choose a service

The Service field accepts a compatible runtime URL without rebuilding. Browser
storage remembers the service URL and selected session per service; switching
services resets loaded histories. The client uses `stocker-runtime-v1` and omits
browser credentials. It does not emulate the LangGraph SDK protocol.

A remote service must implement this API and permit the UI origin through CORS.
Remote authentication, TLS deployment, and credential management remain future
work; no remote deployment has been verified.

## Serve built assets with FastAPI

```bash
pnpm --dir studio build
APP_STATIC_DIRECTORY=../studio/dist make dev
```

When opened at the backend origin, the UI defaults to that origin for API calls.
FastAPI provides SPA navigation fallback while retaining API errors. Vite does
not load local dotenv files (`envDir: false`); service selection is browser-side.

## Checks

```bash
pnpm --dir studio lint
pnpm --dir studio build
pnpm --dir studio exec playwright install chromium
pnpm --dir studio test
```

With an existing Google Chrome installation, use
`STUDIO_BROWSER_CHANNEL=chrome pnpm --dir studio test` instead of downloading
a browser. Fixture tests cover chat, inspection, resume input, service switching,
SSE framing/reconnect, and errors. Live browser tests are opt-in using
`STUDIO_LIVE_API_URL` and must target a runtime with deterministic test graphs
(`echo` and `review`), never a live model. Normal UI usage calls the configured
graph only when you submit a message, resume, or recovery request.

The retained Markdown, syntax highlighting, and UI components originate from
[LangChain Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui), revision
`28cfb43a62b7179ed4065dd761e16ece8c29d983`. See [LICENSE](LICENSE) and the historical
[upstream documentation](UPSTREAM.md). The app-local manifest and pnpm lock own
frontend dependencies; there is no root pnpm workspace.

# Studio Backend Integration

Studio is an implemented React + Vite client for the Agent backend. It has no
dedicated application backend or Node server. It uses `stocker-runtime-v1`
HTTP endpoints and SSE directly.

## Run and verify

Requires Node.js 22.12+, pnpm 12.10.1, and a configured Agent runtime.
From the repository root:

```bash
pnpm --dir studio install --frozen-lockfile
make dev-agent
```

In another terminal:

```bash
make studio
```

`make studio` runs `pnpm --dir studio run dev` with hot reload at
`http://127.0.0.1:5173`. The default API is `http://127.0.0.1:8000`.
From `studio/`, the equivalent command is `pnpm run dev`.

```bash
pnpm --dir studio lint
pnpm --dir studio build
pnpm --dir studio test
```

Browser tests need an installed supported browser. See the
[Studio test guide](../../studio/README.md#checks) for browser setup and opt-in
live tests. Fixture tests do not verify production database or model access.

## Runtime integration

| UI operation | Agent contract |
| --- | --- |
| Discover service and graphs | `/info`, `/api/graphs` |
| Select assistant and session | `/api/assistants`, `/api/sessions` |
| Submit a message, resume or recover | `POST /api/sessions/{session_id}/runs` |
| Inspect or cancel execution | `/api/runs/{run_id}`, `/api/runs/{run_id}/cancel` |
| Read conversation and saved state | `/api/sessions/{session_id}/state` |
| Inspect or compare checkpoints | `/api/sessions/{session_id}/checkpoints` and `/checkpoints/compare` |
| Observe execution | `/api/runs/{run_id}/events` and `/events/stream` |

Messages come from checkpoint-backed state. SSE delivers durable observation
events with reconnect cursors; per-token text streaming is not implemented.
HTTP acceptance and completed execution are separate states in the UI.

## Client structure and configuration

Source lives in `studio/src/`:

- `runtime/client.ts`: HTTP client, errors, SSE framing, and reconnect handling.
- `runtime/types.ts`: runtime data and submission contracts.
- `components/runtime/workspace.tsx`: service, session, and execution coordination.
- `components/runtime/conversation.tsx`: messages, composer, resume, and recovery.
- `components/runtime/inspection.tsx`: execution events, state, and checkpoints.
- `components/thread/`: Markdown and syntax rendering.

The Service field selects a compatible API without rebuilding. Browser storage
remembers service/session selections; switching services resets loaded histories.
Requests omit browser credentials. Vite uses `envDir: false` and does not load
local dotenv files. Each frontend owns its manifest and pnpm lockfile.

## Static hosting

To serve built assets through the Agent backend:

```bash
pnpm --dir studio build
APP_STATIC_DIRECTORY=../studio/dist make dev-agent
```

At the backend origin, the client defaults to that origin. Separate origins need
Agent CORS configuration. `pnpm --dir studio start` previews built assets at
port 3000; use the development command for hot reload. Remote authentication and
TLS deployment remain future work.

See [Studio architecture](architecture.md) and
[Agent backend](../agent/backend.md).

# Chat Backend Integration

Chat is reserved for a user-facing frontend chat bubble connected to Agent.
`chat/` contains a README placeholder only. No standalone chat application,
embeddable widget, package manifest, development command, or dedicated backend
is implemented.

Studio already has a conversation component. It remains part of the development
UI and is not a packaged Chat widget.

## Available backend

Chat is intended to use the existing Agent runtime. Start that backend using
the [Agent setup guide](../../agent/README.md):

```bash
uv sync --project agent --locked
make dev-agent
```

Agent listens at `http://127.0.0.1:8000`. These commands do not launch Chat.
`GET /info` identifies `stocker-runtime-v1`; `/docs` exposes the current contract.
The only registered workflow is `echo`, not a completed company-research service.

## Intended contract reuse

| Chat action | Existing Agent contract |
| --- | --- |
| Select a workflow configuration | `/api/graphs`, `/api/assistants` |
| Start or continue a conversation | `/api/sessions` and a stable session ID |
| Send a message | `POST /api/sessions/{session_id}/runs` with an idempotency key |
| Read saved messages | `GET /api/sessions/{session_id}/state` |
| Observe completion and errors | Run status and `/api/runs/{run_id}/events/stream` |
| Cancel execution | `POST /api/runs/{run_id}/cancel` |
| Resume or acknowledge recovery | Run submissions with `resume` or `recover` actions |

These endpoints are implemented in Agent; their use by Chat is planned. Saved
messages come from checkpoint state. SSE provides durable observations, not
per-token output. Disconnecting from the stream does not cancel the run.

## Configuration and delivery

Model credentials, tools, and database access remain backend concerns. A separate
browser origin would require Agent CORS configuration. Authentication, user/session
authorization, embedding policy, and remote deployment need design before a
public widget can be delivered. No Chat port or hosting mechanism is selected.

Chat will own its manifest and lockfile when implemented. There is no Chat build
or test command yet. The [Studio client](../studio/backend.md) is an implementation
reference for transport behavior, not a verified Chat integration.

See [Chat architecture](architecture.md) and [Agent backend](../agent/backend.md).

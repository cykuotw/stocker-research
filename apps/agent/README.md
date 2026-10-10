# Stocker Agent

Python backend for Taiwan equity research, using FastAPI, LangGraph, and
PostgreSQL. The skill-driven `echo` graph is implemented; research workflows and
data integrations are planned. No official Agent Server, LangSmith account,
cloud license, or Redis is required. Tracing is disabled at startup.

## Local setup

Requires Python 3.14+, `uv`, and PostgreSQL 16. Use a persistent local database
named `stocker_agent_runtime`. The application login needs CONNECT and CREATE on
that database and owns the `runtime` and `checkpoints` schemas; it does not need
SUPERUSER, CREATEDB, or CREATEROLE.

Supply credentials through process environment or an operator-managed
`apps/agent/.env`:

| Variable | Meaning |
| --- | --- |
| `DB_HOST` / `DB_PUBLIC_HOST` | PostgreSQL hostname; default `127.0.0.1` |
| `DB_PORT` | Host-mapped port; default `5433` |
| `DB_USER` | Application login; default `stocker_agent_app` |
| `DB_PASSWORD` | Application password |
| `DB_NAME` | Must be `stocker_agent_runtime` |
| `DATABASE_URI` | Optional PostgreSQL URI or libpq string replacing DB fields |
| `GOOGLE_API_KEY` | Required to execute the Gemini echo graph |

From the repository root:

```bash
uv sync --project apps/agent --locked
make dev
```

`make dev` starts FastAPI with reload at `http://127.0.0.1:8000`. The shared
configuration layer loads `apps/agent/.env` automatically, including DB,
model, and skill settings; `uv --env-file` is not required. The file is optional
when all required credentials are supplied through process environment.

Non-secret settings belong in `settings.toml`: `[app]`, `[skills]`, and
`[llm-models]`. Settings precedence is constructor values, process environment,
`.env`, TOML, then defaults. `.env.local` is not loaded. Keep credentials
out of TOML and browser configuration. Restart after changing configuration.

## Backend structure and persistence

`src/stocker_agent/server.py` is the FastAPI entrypoint (`app = create_app()`).
The `app/` package separates application assembly, resources, and HTTP transport:

- `factory.py`: one settings snapshot, CORS, errors, routers, and optional static UI.
- `lifespan.py`: eager PostgreSQL/checkpointer/graph startup, worker ownership,
  recovery, and shutdown. The worker stops before database pools close.
- `context.py` and `dependencies.py`: typed application resources and reusable
  `Annotated[..., Depends(...)]` accessors.
- `routers/`: system, assistants/sessions, runs, and inspection/SSE endpoints.
- `service.py`: session/run operations and checkpoint/event queries.
- `runner.py`: durable graph execution, cancellation, and recovery.
- `repository.py`: parameterized SQL, transactions, and runtime migrations.

Resources are created once per application lifespan. HTTP dependencies retrieve
those resources; services and the worker use constructor injection. Tests can
replace dependency functions with `app.dependency_overrides` and supply a test
lifespan without opening PostgreSQL or calling a model. Missing DB credentials
fail at startup rather than during application assembly.

Custom metadata lives in the `runtime` schema. LangGraph's `AsyncPostgresSaver`
manages the `checkpoints` schema and owns messages, graph state, and interrupts.
The session UUID maps to LangGraph `thread_id`; each turn has its own `run_id`.
Research-result storage is separate from runtime persistence.

Startup applies checksummed migrations and checkpoint setup automatically.
Run one server process per database: an advisory lock rejects another instance,
and losing that connection stops execution. The single worker executes persisted
pending runs sequentially; overlapping runs within a session are rejected.

## API and execution

Use `http://127.0.0.1:8000/docs` or `/openapi.json` for the complete API contract.
`/health` checks PostgreSQL and worker readiness; `/info` identifies the protocol.

| Operation | Endpoint |
| --- | --- |
| Discover graphs | `GET /api/graphs` |
| Create/list assistants | `POST` / `GET /api/assistants` |
| Create/list sessions | `POST` / `GET /api/sessions` |
| Submit/list runs | `POST` / `GET /api/sessions/{session_id}/runs` |
| Inspect/cancel a run | `GET /api/runs/{run_id}`, `POST /api/runs/{run_id}/cancel` |
| Current state and history | `GET /api/sessions/{session_id}/state`, `GET /api/sessions/{session_id}/checkpoints` |
| Compare checkpoints | `GET /api/sessions/{session_id}/checkpoints/compare?left=...&right=...` |
| Inspect/stream events | `GET /api/runs/{run_id}/events`, `GET /api/runs/{run_id}/events/stream` |

Create an assistant with `{"graph_id":"echo","name":"Echo"}`, then create a
session with its `assistant_id`. Submit each turn to the same session's runs URL:

```json
{
  "input": {"messages": [{"role": "user", "content": "hello"}]},
  "idempotency_key": "a-unique-key-per-turn"
}
```

HTTP 202 means the run is persisted. Exact retries with the same session/key
return the existing run; changed bodies or overlapping runs return HTTP 409.
Disconnecting from SSE does not cancel an accepted run.

Resume an interrupted session using a new key:

```json
{"action":"resume","resume":true,"idempotency_key":"review-1"}
```

After a failed, cancelled, or unfinished run, explicitly acknowledge replay:

```json
{"action":"recover","acknowledge_replay":true,"idempotency_key":"recovery-1"}
```

Pending work survives restart and executes automatically. Unfinished running
work becomes `recovery_required` and waits for acknowledgement. Recovery uses
saved checkpoints; unfinished nodes may replay. Keep side effects idempotent.
Cancellation is cooperative and cannot undo a completed external side effect.

Durable events expose run lifecycle, graph/node execution, model/tool activity,
and checkpoint references. Inspection metadata includes nullable node, model,
skill, tool, duration, and usage fields. Final messages and node updates are
observable; per-token streaming is not implemented. See
[event fixtures](tests/fixtures/runtime-events.json).

SSE uses `event_id` as its `id`; reconnect with `Last-Event-ID` or `?after=`.
Event history uses an exclusive numeric `after` cursor. Other lists use UUID
`after` cursors; checkpoint history is newest first with `before=checkpoint_id`.
Lists accept `limit` from 1–200, default 50. Events and checkpoints are retained;
automatic pruning and deletion APIs are not implemented.

## Skills and models

Local research skills belong in `apps/agent/skills/` (Git-ignored). Each directory
contains `SKILL.md` with name/description frontmatter and `manifest.yaml` with
matching `id` and `version`. Optional fields include `required_tools`,
`allowed_agents`, `llm_model`, and `status`. Skills cannot grant tool permissions.

`SKILL_MODE=local|s3` selects the source; `SKILL_LOCAL_PATH` defaults to `./skills`,
resolved from `apps/agent`. S3 requires `SKILL_S3_BUCKET`; `SKILL_S3_PREFIX`
defaults to `skills`. `SkillRegistry.refresh()` updates subsequent snapshots;
failed refreshes retain the previous snapshot. There is no HTTP refresh endpoint
or automatic refresh. Optional references and durable skill-version pinning are
not implemented; S3 loading has only been tested with a fake client.

`ModelProvider` exposes `instant`, `standard`, and `complex` tiers. Gemini is the
supported provider; model IDs, timeouts, and retries are configured in
`settings.toml` and can be overridden with `LLM_*` environment variables.
The echo graph uses its skill's tier and the `print_user_message` tool.
Clients are lazy and cached; no automatic tier fallback is implemented.

## UI and checks

`apps/studio` is the React + Vite client for this API, providing sessions, chat,
execution events/traces, state, checkpoints, and interrupt/resume controls. See
[Studio setup](../studio/README.md). Optional
`APP_STATIC_DIRECTORY` serves a built static UI; missing assets allow API-only
startup, and unknown API routes keep their errors instead of falling through to
the UI. Relative paths resolve from `apps/agent`. `APP_CORS_ORIGINS` accepts a
JSON list, defaulting to local ports 3000 and 5173. Remote authentication and TLS
are not implemented; the server binds to loopback by default.

From the repository root:

```bash
make test-agent
make ruff
```

PostgreSQL integration tests require `TEST_RUNTIME_DATABASE_URI` pointing to
`stocker_agent_runtime`; otherwise they skip. They create unique test records
without resetting schemas. Tests use deterministic graphs and fake models;
live Gemini verification is manual.

Missing Gemini keys or model IDs fail the run with `model_configuration_missing`
and a setting name, without exposing credentials. Configure the missing setting,
restart the backend, then acknowledge recovery for the failed session. HTTP 202
means the run was accepted; its stored status determines whether execution succeeded.

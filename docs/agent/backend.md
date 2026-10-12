# Stocker Agent Backend

Custom FastAPI runtime for LangGraph workflows. Sessions, assistants, durable
runs, inspection events, checkpoints, skill loading, model adapters, and the
skill-driven `echo` graph are implemented. Company research, quantitative-data
integration, Knowledge retrieval, and research-artifact storage are planned.

## Run and verify

Requires Python 3.14+, `uv`, and PostgreSQL 16. Configure the runtime database
and model credentials using the [Agent setup guide](../../agent/README.md).
From the repository root:

```bash
uv sync --project agent --locked
make dev-agent
```

The development server runs with reload at `http://127.0.0.1:8000`.
`make dev` is an alias for `make dev-agent`.

```bash
make test-agent
make ruff
```

Database integration tests require `TEST_RUNTIME_DATABASE_URI`; otherwise they
skip. Automated model tests use fake responses. These checks do not establish
live database, model, or external-data readiness.

## HTTP contract

| Operation | Endpoint | Meaning |
| --- | --- | --- |
| Readiness | `GET /health` | Checks database and worker readiness |
| Runtime identity | `GET /info` | Reports `stocker-runtime-v1` |
| API reference | `GET /docs`, `GET /openapi.json` | Complete current HTTP contract |
| Graph discovery | `GET /api/graphs` | Registered workflow IDs; currently `echo` |
| Assistants | `GET`, `POST /api/assistants` | Configurations selecting a graph |
| Sessions | `GET`, `POST /api/sessions` | Conversation identity |
| Runs | `GET`, `POST /api/sessions/{session_id}/runs` | Persist or list execution requests |
| Run inspection | `GET /api/runs/{run_id}` | Execution status |
| Cancellation | `POST /api/runs/{run_id}/cancel` | Cooperative cancellation |
| State | `GET /api/sessions/{session_id}/state` | Checkpoint-backed conversation and workflow state |
| Checkpoints | `GET /api/sessions/{session_id}/checkpoints` | Saved checkpoint history |
| Events | `GET /api/runs/{run_id}/events` | Durable observation history |
| Event stream | `GET /api/runs/{run_id}/events/stream` | SSE observation with reconnect cursors |

Create an assistant and session before submitting a turn. Use the same session
for conversation continuity and a unique `idempotency_key` per request. HTTP 202
means acceptance into the persisted queue; the run status reports the outcome.
Interrupts accept resume requests. Failed, cancelled, or unfinished executions
require explicit replay acknowledgement before recovery. Examples and checkpoint
comparison are documented in the [API guide](../../agent/README.md#api-and-execution).

## Backend structure

Source lives in `agent/src/stocker_agent/`:

- `server.py` and `app/core/`: assembly, resource lifespan, recovery, and shutdown.
- `app/routers/`, `app/models/`, `app/dependencies/`: HTTP transport and typed contracts.
- `app/services/`: session operations and durable graph execution.
- `app/database/`, `app/migrations/`, `app/repositories/`: runtime persistence.
- `graph_runtime/` and `graphs/`: registered graph factories and workflows.
- `agent_runtime/`: bounded agents and their tool policies.
- `skills/`, `tools/`, `llm/`: research-skill loading, tool resolution, and model tiers.

Python dependencies, settings, tests, and the lockfile belong to `agent/`.
Application research skills belong to `agent/skills/`.

## Configuration and persistence

Non-secret settings use `agent/settings.toml`. Precedence is constructor values,
process environment, `agent/.env`, TOML, then defaults. Restart after settings
changes. Keep database and model credentials out of browser configuration.

The database is `stocker_agent_runtime`. Application metadata and events use
`runtime`; LangGraph manages `checkpoints` and owns graph state, messages, and
interrupts. Startup applies runtime migrations and checkpointer setup. One server
process owns execution per database; the worker processes persisted runs sequentially.

Studio is the implemented client. Optional `APP_STATIC_DIRECTORY` serves its built
assets; `APP_CORS_ORIGINS` configures separate browser origins. Authentication,
remote deployment, and transient token streaming are not implemented.

See [Agent architecture](architecture.md) and the
[Studio integration guide](../studio/backend.md).

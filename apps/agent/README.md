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

- `core/`: application factory, resource context, errors, and eager lifespan
  startup/recovery/shutdown. The worker stops before database pools close.
- `dependencies/`: reusable `Annotated[..., Depends(...)]` accessors.
- `routers/`: system, assistants/sessions, runs, and inspection/SSE endpoints.
- `services/`: session/run operations, checkpoint/event queries, and durable
  graph execution, cancellation, and recovery.
- `database/`: application-scoped database factory, SQLAlchemy table mappings,
  and migration execution. `migrations/` retains immutable runtime DDL resources.
- `repositories/`: SQLAlchemy Core queries with bound values and transactions.
- `models/`: graph, assistant, session, run, event, and checkpoint HTTP models.
- `utils/`: public-data serialization and redaction.

Resources are created once per application lifespan. HTTP dependencies retrieve
those resources; services and the worker use constructor injection. Tests can
replace dependency functions with `app.dependency_overrides` and supply a test
lifespan without opening PostgreSQL or calling a model. Missing DB credentials
fail at startup rather than during application assembly.

`DatabaseFactory` opens one SQLAlchemy async engine for runtime metadata, one
psycopg pool for LangGraph checkpoints, and a dedicated advisory-lock connection
per application lifespan. Operations borrow connections from their pool; no
single connection is shared across concurrent transactions. The worker stops
before database resources close, including when startup fails.

Configure database limits under `[app]` in `settings.toml`:

```toml
runtime_pool_size = 5
checkpoint_pool_size = 5
connect_timeout_seconds = 5
pool_timeout_seconds = 5
statement_timeout_seconds = 30
lock_timeout_seconds = 5
migration_timeout_seconds = 120
shutdown_timeout_seconds = 10
```

Each setting can be overridden through `APP_<UPPERCASE_NAME>` in the process
environment or `.env`. Replace the former `max_pool_size` / `APP_MAX_POOL_SIZE`
with the two pool-size settings. The connection ceiling per server is
`runtime_pool_size + checkpoint_pool_size + 1` for ownership (11 by default).
There is no runtime pool overflow. Connection timeout also applies when using
`DATABASE_URI`; pool timeout bounds acquisition and checkpoint-pool startup.
Query and lock timeouts apply to new connections in both pools. Migration setup
temporarily uses the migration statement timeout and retains the lock timeout;
normal query settings are restored afterward. These are per-statement limits,
not a deadline for the whole graph or migration sequence. Shutdown bounds the
worker-stop wait; if it times out, shutdown reports an error and unfinished runs
are handled by startup recovery. Python cancellation must remain cooperative.

Runtime queries use SQLAlchemy Core expressions for selects, inserts, updates,
pagination, row locks, and `SKIP LOCKED`. Values remain bound parameters.
LangGraph continues using its supported psycopg checkpointer. The existing
checksummed migration SQL is unchanged and runs as trusted bundled DDL through
the engine's psycopg driver; table mappings do not manage or alter schemas.

`graphs/` contains workflow implementations. `graph_runtime/` contains the
catalog, registry, and shared-resource contract. Graph factories are explicitly registered in `graph_runtime/catalog.py`. Startup creates
one `GraphResources` bundle with the PostgreSQL checkpointer, model router, skill
registry, and tool registry. `GraphRegistry` passes that same bundle to each
factory and validates the compiled result. Graph modules do not create instances
at import time, and `lifespan.py` contains no per-graph wrappers.

To add a workflow, implement `build_graph(resources: GraphResources)` in its
graph module and register it under a unique ID in `GRAPH_FACTORIES`:

```python
GRAPH_FACTORIES = {
    "echo": build_echo_graph,
    "company_research": build_company_research_graph,
}
```

The second entry illustrates a future workflow; only `echo` is currently
registered. Compile with `resources.checkpointer` and reuse `resources.models`,
`resources.skills`, and `resources.tools`. Available tools remain subject to each
graph's policy and the skill manifest. Model clients are initialized on use.
Agent policies live in `agent_runtime/definitions.py`, separate from workflow topology.
`AgentFactory` validates skill status and `allowed_agents`, resolves tools through
`tools/resolver.py`, selects the skill's model tier, and builds a LangChain agent.
Only required tools that are both authorized and registered are exposed; missing
or disallowed requirements fail before model construction. Skills cannot grant
permissions. `SkillAgent` preserves request configuration and adds agent/skill
metadata and the definition's recursion limit. Graph nodes retain input/output
adapters; reusable agents do not read or mutate workflow state directly. The
echo node uses `ECHO_AGENT` and keeps its conversation-delta conversion locally.
Tests can override `graph_factories` and `graph_resources_factory` in `create_app`
to inject deterministic graphs/resources without loading local skills or models.

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

`ModelRouter` maps `instant`, `standard`, and `complex` tiers to provider/model
routes. `ModelProvider` is the abstract client factory/cache contract, implemented
by `GeminiProvider` and `OpenRouterProvider`. The echo graph selects only its
skill's tier and uses the `print_user_message` tool. Clients are lazy and cached
by model ID within each provider; tiers sharing a provider/model reuse a client.

Configure routes in `settings.toml`:

```toml
[llm-models]
timeout_seconds = 600
max_retries = 2

[llm-models.instant]
provider = "gemini"
model = "gemini-3.5-flash-lite"

[llm-models.standard]
provider = "gemini"
model = "gemini-3.8-flash"

[llm-models.complex]
provider = "openrouter"
model = "anthropic/claude-opus-4.6"
```

Keep `GOOGLE_API_KEY` and `OPENROUTER_API_KEY` in `.env` or the process
environment. A key is required only when its provider is used. Provider/model
overrides use `LLM_INSTANT__PROVIDER`, `LLM_INSTANT__MODEL`, and the corresponding
`STANDARD`/`COMPLEX` names. These replace the old `LLM_PROVIDER` and
`LLM_*_MODEL` variables; existing overrides must be renamed. Timeout/retry
overrides remain `LLM_TIMEOUT_SECONDS` and `LLM_MAX_RETRIES`. Restart after changes.
Both providers use the same timeout in seconds; the OpenRouter adapter converts
it to SDK milliseconds. There is no automatic model/tier fallback. OpenRouter
model calls remain manually verified; automated tests use fake responses.

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

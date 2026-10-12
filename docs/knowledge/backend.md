# Stocker Knowledge Backend

Independent FastAPI service for the Stocker document and knowledge platform.
The HTTP foundation and model adapters are implemented; ingestion, extraction,
persistence, retrieval, and MCP integration are planned.

## Run and verify

Requires Python 3.14+ and `uv`. From the Stocker Research repository root:

```bash
uv sync --project knowledge --locked
make dev-knowledge
make test-knowledge
make ruff
```

`make dev-knowledge` binds the development server to loopback on port 8001. For another port:

```bash
uv run --project knowledge fastapi dev --port 8010
```

| Operation | Endpoint | Meaning |
| --- | --- | --- |
| Process liveness | `GET /health` | The HTTP process responds; no external readiness check |
| Service information | `GET /info` | Identity and implemented / planned capabilities |
| OpenAPI | `GET /docs`, `GET /openapi.json` | Current HTTP contract |

Chat assistants, sessions, runs, and checkpoints are not exposed by this service.
No document or MCP endpoint is exposed until the corresponding capability is implemented.

## Backend structure

All backend source lives in `src/knowledge/`, packaged as `stocker-knowledge`
and imported as `knowledge`. Python settings, dependencies and tooling live
in the `knowledge/` service directory:

- `server.py`: FastAPI entrypoint, delegating to `app/core/factory.py`.
- `app/core/`: application assembly and middleware configuration.
- `app/routers/`: HTTP endpoints grouped by concern.
- `app/models/`: public HTTP request and response models.
- `config/`: environment and TOML configuration.
- `llm/`: provider-neutral model routing and lazy clients.
- `tests/`: backend tests alongside `src/` in the `knowledge/` service directory.

As features are implemented, resource lifecycle code belongs in `app/core/`,
FastAPI dependency accessors in `app/dependencies/`, use cases in `app/services/`,
database setup in `app/database/`, SQL migrations in `app/migrations/`, and
queries in `app/repositories/`. These additional layers are not implemented yet.
Document-processing and retrieval modules remain separate from HTTP handlers.

`dashboard/` is reserved for the document-processing dashboard and monitoring UI.
It currently contains documentation only and is not required for backend development.

## Configuration

Non-secret settings belong in `settings.toml`. Precedence is constructor values,
process environment, TOML, then defaults. The service does not automatically load
dotenv files or secret directories. Operator tooling may supply process environment.
The editable source checkout resolves `settings.toml` from the `knowledge/` service directory,
independently of the shell's working directory. Restart after changing settings.

| Setting | Purpose |
| --- | --- |
| `KNOWLEDGE_CORS_ORIGINS` | Optional JSON list of browser origins; defaults to none |
| `LLM_INSTANT__PROVIDER` / `LLM_INSTANT__MODEL` | Instant-tier route |
| `LLM_STANDARD__PROVIDER` / `LLM_STANDARD__MODEL` | Standard-tier route |
| `LLM_COMPLEX__PROVIDER` / `LLM_COMPLEX__MODEL` | Complex-tier route |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | Model client timeout and retry configuration |
| `GOOGLE_API_KEY` | Gemini credential, required only when using Gemini |
| `OPENROUTER_API_KEY` | OpenRouter credential, required only when using OpenRouter |

The checked-in settings select initial Gemini routes matching Agent:

| Tier | Model ID | Intended Knowledge tasks |
| --- | --- | --- |
| `instant` | `gemini-3.5-flash-lite` | Document classification and simple extraction |
| `standard` | `gemini-3.8-flash` | Targeted extraction and evidence organization |
| `complex` | `gemini-3.8-flash` | Cross-section reasoning and contradiction analysis |

These task assignments are planned; extraction components are not implemented.
The IDs are listed in Google's [Flash-Lite documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
and [Flash documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
Account availability and extraction quality have not been verified. Tiers may
share a provider/model client; selecting `complex` does not set a separate thinking
budget. There is no automatic provider fallback. Credentials are excluded from
TOML and settings representations.

The service does not consume Agent database or research-skill configuration.
Knowledge database and storage configuration will be introduced with persistence,
using separate service ownership. PostgreSQL, object storage, and external model
calls have not been verified by this foundation's automated tests.

## Tests and packaging

Tests use fake model responses and do not require external services or credentials.
Configuration tests verify precedence, unsupported fields, and absence of implicit
credential-file loading. Service tests verify startup and the exposed API boundary.

```bash
uv run --project knowledge ty check knowledge/src
uv build --project knowledge
```

# Dashboard Backend Integration

Dashboard is reserved for the Knowledge management UI. `dashboard/` currently
contains documentation only: no frontend application, package manifest, build,
development server, or Dashboard-specific backend exists.

## Available backend

The independent Knowledge service has an implemented HTTP foundation and lazy
model adapters. Start or check that backend from the repository root:

```bash
uv sync --project knowledge --locked
make dev-knowledge
make test-knowledge
```

These commands run and test Knowledge, not Dashboard. The development backend
listens at `http://127.0.0.1:8001`.

| Endpoint | Available behavior |
| --- | --- |
| `GET /health` | HTTP-process liveness; no external readiness check |
| `GET /info` | Service identity and implemented/planned capabilities |
| `GET /docs`, `GET /openapi.json` | Current HTTP contract |

Document ingestion, extraction, persistence, retrieval, and MCP are planned.
No document upload, processing-job, review, or retrieval endpoint is exposed yet.
Agent sessions, runs, and checkpoints are not Knowledge endpoints.

## Planned integration

| Dashboard function | Backend responsibility | Status |
| --- | --- | --- |
| Document import | Validate authorized sources and create ingestion work | Planned |
| Processing progress | Report document-job status and stage failures | Planned |
| Extraction review | Read evidence and submit review decisions | Planned |
| Source inspection | Retrieve document versions, sections, and provenance | Planned |
| Retrieval evaluation | Query published knowledge with source references | Planned |

These are intended responsibilities, not fixed HTTP routes. Define public
Knowledge contracts when their capabilities are implemented; the UI must not
depend on database tables or Agent runtime repositories.

## Configuration and checks

Knowledge configuration and tests remain under `knowledge/`. Browser origins
can be configured with `KNOWLEDGE_CORS_ORIGINS`. No Dashboard origin, port,
authentication flow, or frontend dependency stack is selected here.

Dashboard will own its frontend manifest and lockfile when implemented.
There is no Dashboard startup or test command yet. No UI or backend integration
has been verified for Dashboard.

See [Dashboard architecture](architecture.md),
[Knowledge backend](../knowledge/backend.md), and
[Dashboard placeholder](../../dashboard/README.md).

# Knowledge Architecture

Knowledge owns document processing, structured qualitative knowledge, provenance,
and retrieval. HTTP, database connections, and model adapters are implemented.
Document pipelines, domain persistence, retrieval, and MCP are planned.
PostgreSQL/pgvector and Haystack are selected for retrieval; the pipeline is not implemented.

- Keep Knowledge independent of Agent state and runtime repositories. HTTP and
  future MCP transports share application services.
- Use separate databases and logins for Agent and Knowledge. Domain migrations
  and any future checkpointer retain separate ownership.
- Planned processing: import → parse → section → extract → validate/review → publish
  → optional indexing. Queries consume published data. LangGraph owns durable
  processing/review; Haystack composes bounded indexing and retrieval steps.
- Prefer structured knowledge, then document sections, then keyword/vector search.
  Rebuildable search indexes do not replace the source evidence archive.
- Preserve provenance, units, source versions, evidence locations, confidence,
  extractor version, and timestamps. Distinguish facts, attributed forecasts,
  contradictions, and inference; expose missing/stale data and as-of semantics.
- Agent owns research conclusions. Knowledge returns bounded, authorized results
  with source references through public contracts.

| Concern | Source |
| --- | --- |
| Assembly and resource lifecycle | [server.py](../../knowledge/src/knowledge/server.py), [app/core/](../../knowledge/src/knowledge/app/core/) |
| HTTP contracts | [routers/](../../knowledge/src/knowledge/app/routers/), [models/](../../knowledge/src/knowledge/app/models/) |
| Settings and precedence | [config/](../../knowledge/src/knowledge/config/), [settings.toml](../../knowledge/settings.toml) |
| Database pool and readiness | [app/database/](../../knowledge/src/knowledge/app/database/), [app/dependencies/](../../knowledge/src/knowledge/app/dependencies/) |
| Model adapters | [llm/](../../knowledge/src/knowledge/llm/) |
| Dependencies and verification | [pyproject.toml](../../knowledge/pyproject.toml), [tests/](../../knowledge/tests/), [Makefile](../../Makefile) |

The application does not provision databases or extensions at startup.
See [system architecture](../architecture.md) and [Knowledge README](../../knowledge/README.md).

# Stocker Knowledge

Independent document and knowledge service within Stocker Research. It provides
source-traceable qualitative knowledge and retrieval for Agent and other consumers.
Research conclusions belong to Agent; quantitative data collection remains in Stocker.

The implemented FastAPI foundation exposes `/health` and `/info`, with lazy model
adapters. Ingestion, extraction, persistence, retrieval, embeddings, and MCP are
planned. Health reports process liveness, not database or retrieval readiness.

## Development

From the Stocker Research repository root:

```bash
uv sync --project knowledge --locked
make dev-knowledge
make test-knowledge
make ruff
```

The development server uses port 8001. Alternatively, from `knowledge/`:

```bash
uv run fastapi dev --port 8001
uv run pytest tests
uv run ty check src
uv build
```

Python source lives in `src/knowledge/`, with service-local tests, settings,
manifest, and lockfile. Settings resolve from this service directory regardless
of the working directory. Knowledge does not automatically load dotenv files.
No database or model credentials are required to start the current foundation.

The separate `../dashboard/` directory reserves the document-processing,
knowledge inspection, and retrieval evaluation UI. No frontend is implemented yet.

See [backend configuration](../docs/knowledge/backend.md) and
[service architecture](../docs/knowledge/architecture.md).

# Stocker Knowledge

Independent document and evidence service. HTTP, database connections, and model
adapters are implemented; document processing, retrieval, and MCP are planned.

- [Architecture and source map](../docs/knowledge/architecture.md)
- [Requirements and dependencies](pyproject.toml)
- [Non-secret settings](settings.toml)
- [Planned management UI](../dashboard/README.md)

Connection credentials come from environment or service-local `.env`; supported
fields are defined in [config/database.py](src/knowledge/config/database.py).
Development/check commands: `make dev-knowledge`, `make test-knowledge`, `make ruff`;
see [Makefile](../Makefile).

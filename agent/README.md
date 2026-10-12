# Stocker Agent

FastAPI + LangGraph research runtime. Sessions, runs, checkpoints, inspection,
and the `echo` workflow are implemented; research workflows are planned.

- [Architecture and source map](../docs/agent/architecture.md)
- [Requirements and dependencies](pyproject.toml)
- [Non-secret settings](settings.toml)
- [Development UI](../studio/README.md)

Connection credentials come from environment or service-local `.env`; supported
fields are defined in [config/app.py](src/stocker_agent/config/app.py).
Development/check commands: `make dev-agent`, `make test-agent`, `make ruff`;
see [Makefile](../Makefile).

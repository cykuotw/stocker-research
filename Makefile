.PHONY: dev ruff ruff-fix studio test-agent

dev:
	cd apps/agent && uv run fastapi dev

ruff:
	uv run --project apps/agent ruff check apps/agent
	uv run --project apps/agent ruff format --check apps/agent

ruff-fix:
	uv run --project apps/agent ruff check --fix apps/agent
	uv run --project apps/agent ruff format apps/agent
	uv run --project apps/agent ruff check apps/agent

test-agent:
	uv run --project apps/agent pytest apps/agent/tests

studio:
	pnpm --dir apps/studio build
	@echo "Stocker Studio: http://127.0.0.1:3000"
	pnpm --dir apps/studio start

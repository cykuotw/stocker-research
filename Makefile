.PHONY: dev dev-agent dev-knowledge ruff ruff-fix studio test test-agent test-knowledge

dev: dev-agent

dev-agent:
	cd agent && uv run fastapi dev --port 8000

dev-knowledge:
	cd knowledge && uv run fastapi dev --port 8001

ruff:
	uv run --project agent ruff check agent/src agent/tests
	uv run --project agent ruff format --check agent/src agent/tests
	uv run --project knowledge ruff check knowledge/src knowledge/tests
	uv run --project knowledge ruff format --check knowledge/src knowledge/tests

ruff-fix:
	uv run --project agent ruff check --fix agent/src agent/tests
	uv run --project agent ruff format agent/src agent/tests
	uv run --project knowledge ruff check --fix knowledge/src knowledge/tests
	uv run --project knowledge ruff format knowledge/src knowledge/tests
	$(MAKE) ruff

test: test-agent test-knowledge

test-agent:
	uv run --project agent pytest agent/tests

test-knowledge:
	uv run --project knowledge pytest knowledge/tests

studio:
	pnpm --dir studio run dev

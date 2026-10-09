.PHONY: dev ruff studio test-agent

dev:
	cd apps/agent && LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false uv run langgraph dev --no-browser

ruff:
	uv run --project apps/agent ruff check apps/agent
	uv run --project apps/agent ruff format --check apps/agent

test-agent:
	uv run --project apps/agent pytest apps/agent/tests

studio:
	pnpm --dir apps/studio build
	@echo "Agent Chat UI: http://localhost:3000"
	pnpm --dir apps/studio start

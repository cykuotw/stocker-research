.PHONY: dev ruff studio test-agent

dev:
	cd apps/agent && LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false uv run langgraph dev --no-browser

ruff:
	uv run --project apps/agent ruff check apps/agent
	uv run --project apps/agent ruff format --check apps/agent

test-agent:
	uv run --project apps/agent pytest apps/agent/tests

studio:
	@echo "Agent Chat UI: http://localhost:3000 (use the Local URL below if the port changes)"
	pnpm --dir apps/studio dev

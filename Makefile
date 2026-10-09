.PHONY: dev ruff studio

dev:
	cd apps/agent && uv run langgraph dev --no-browser

ruff:
	uv run --project apps/agent ruff check apps/agent
	uv run --project apps/agent ruff format --check apps/agent

studio:
	@echo "Agent Chat UI: http://localhost:3000 (use the Local URL below if the port changes)"
	pnpm dev:studio

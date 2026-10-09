.PHONY: run dev ruff studio

run:
	uv run --project apps/agent stocker-agent

dev:
	cd apps/agent && uv run langgraph dev

ruff:
	uv run --project apps/agent ruff check apps/agent
	uv run --project apps/agent ruff format --check apps/agent

studio:
	pnpm dev:studio

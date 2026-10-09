.PHONY: run dev ruff

run:
	uv run stocker-agent

dev:
	uv run langgraph dev

ruff:
	uv run ruff check .
	uv run ruff format --check .

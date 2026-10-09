# Stocker Agent

An AI research assistant for Taiwan equities, designed to combine financial data,
company filings, and news into research reports with traceable evidence.
The initial focus is company research and cyclical-bottom analysis.

## Status

This repository currently contains a minimal Python package scaffold. Research
workflows, data integrations, and agent services are planned and not yet implemented.
Automated trading is outside the initial scope.

## Planned architecture

- LangGraph workflows with bounded LangChain agents and reusable research skills.
- Gemini models and Google Search grounding behind provider abstractions.
- PostgreSQL for structured data and research artifacts; object storage for documents.
- LangGraph Agent Server for execution, streaming, checkpoints, and human review.

## Quick start

Requires Python 3.14+, `uv`, and `make`.

```bash
make run
```

The current command runs the scaffold's greeting; it does not perform research yet.

To start the LangGraph development server once a graph and `langgraph.json` are configured:

```bash
make dev
```

This runs `uv run langgraph dev`.

To check Python lint and formatting:

```bash
make ruff
```

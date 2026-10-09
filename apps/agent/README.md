# Stocker Agent

Python backend for Taiwan equity research. Includes a model-free echo graph for
local testing; research workflows and data integrations are planned.

From the repository root, run `make dev` or `make ruff`.
Run `make test-agent` for the backend test suite.
Use `uv sync --project apps/agent --locked` to install Python dependencies.

Run `make dev` to start Agent Server at `http://localhost:2024` with graph ID
`echo`. Send a chat message through Studio to receive `Echo: <your message>`.
No API key is required. Keep application code under `src/stocker_agent/`.

## Research skill configuration

Local application skills belong in `apps/agent/skills/`, which is ignored by Git.
Create it with `mkdir -p apps/agent/skills` from the repository root.
Development-assistant skills are separate from these application skills.

`SkillSettings` in `stocker_agent.config.skills` reads process environment
variables without loading dotenv files:

Keep environment settings under `stocker_agent/config/`, grouped by concern.
The future skill registry and storage loaders belong in separate application modules.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SKILL_MODE` | `local` | `local` or `s3` |
| `SKILL_LOCAL_PATH` | `./skills` | Local filesystem path |
| `SKILL_S3_BUCKET` | empty | Bucket name, required in S3 mode |
| `SKILL_S3_PREFIX` | `skills` | Object prefix within the bucket |

Relative local paths resolve from `apps/agent/`, independently of the working
directory. Source selection and validation are implemented; skill loading,
manual refresh API, and graph integration are not implemented yet. No refresh
interval or automatic polling is planned. The echo graph does not use research
skills. Production will supply these settings through deployment-managed env.

`make dev` disables LangSmith tracing. Future deployments must also keep
`LANGSMITH_TRACING=false` and `LANGCHAIN_TRACING_V2=false`.

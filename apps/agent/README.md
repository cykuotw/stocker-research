# Stocker Agent

Python backend for Taiwan equity research. Includes a skill-driven echo graph for
local testing; research workflows and data integrations are planned.

From the repository root, run `make dev` or `make ruff`.
Run `make test-agent` for the backend test suite.
Use `uv sync --project apps/agent --locked` to install Python dependencies.

Run `make dev` to start Agent Server at `http://localhost:2024` with graph ID
`echo`. Send a chat message through Studio to receive `Echo: <your message>`.
A `GOOGLE_API_KEY` in process environment or `apps/agent/.env` is required. Keep application code under `src/stocker_agent/`.

## Research skill configuration

Local application skills belong in `apps/agent/skills/`, which is ignored by Git.
Create it with `mkdir -p apps/agent/skills` from the repository root.
Development-assistant skills are separate from these application skills.

`SkillSettings` in `stocker_agent.config.skills` reads the `[skills]` section of
`apps/agent/settings.toml`, `apps/agent/.env`, and process environment.

Keep environment settings under `stocker_agent/config/`, grouped by concern.
The future skill registry and storage loaders belong in separate application modules.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SKILL_MODE` | `local` | `local` or `s3` |
| `SKILL_LOCAL_PATH` | `./skills` | Local filesystem path |
| `SKILL_S3_BUCKET` | empty | Bucket name, required in S3 mode |
| `SKILL_S3_PREFIX` | `skills` | Object prefix within the bucket |

Relative local paths resolve from `apps/agent/`, independently of the working
directory. Local and S3 skill loading and explicit in-process refresh are implemented.
The echo graph uses the registry; the manual refresh API is not implemented yet. No refresh
interval or automatic polling is planned. The echo graph loads the `echo-agent` skill. Production will supply these settings through deployment-managed env.

`make dev` disables LangSmith tracing. Future deployments must also keep
`LANGSMITH_TRACING=false` and `LANGCHAIN_TRACING_V2=false`.

## Skill registry

Each skill directory must contain `SKILL.md` with `name` and `description` YAML
frontmatter, and `manifest.yaml` with `id` and `version`. Directory name, skill
name and manifest ID must match. Optional manifest fields are `required_tools`,
`allowed_agents`, `llm_model`, and `status` (`active` or `inactive`). `llm_model`
accepts `instant`, `standard` (default), or `complex`.

```python
from stocker_agent.skills.registry import SkillRegistry

registry = SkillRegistry.from_settings()
run_skills = registry.snapshot()
skill = run_skills["echo-agent"]
instructions = skill.instructions

registry.refresh()  # Explicit reload for subsequent runs
```

Snapshots are immutable and failed refreshes preserve the previous snapshot.
Retain a snapshot for an in-flight run; `content_hash` identifies the loaded
document and manifest. The registry does not execute instructions or grant tools.
It currently loads only the document and manifest, not optional references.
S3 uses the same `<prefix>/<skill-id>/` layout; AWS credentials come from the SDK's
standard credential chain. Updates must not overlap a refresh: immutable published
revisions, durable resume pinning, and refresh coordination across processes remain
to be implemented. S3 loading has been tested with a fake client, not a live bucket.

## Model providers

`ModelProvider` exposes LangChain `BaseChatModel` clients for `instant` (small,
latency-sensitive tasks), `standard` (general analysis), and `complex` (deeper
synthesis). Graph nodes select tiers without importing provider SDK classes:

```python
from stocker_agent.llm import ModelProvider, ModelTier

models = ModelProvider()
model = models.get(ModelTier.STANDARD)
# Or select the tier declared by a loaded skill:
model = models.get(skill.manifest.llm_model)
# In an async graph node: response = await model.ainvoke(messages)
```

Gemini is the currently supported provider. `settings.toml` selects
`gemini-3.5-flash-lite` for instant, `gemini-3.8-flash` for standard, and
`gemini-3.1-pro-preview` for complex. The complex model is a preview; verify
account availability and evaluate results before production use.
Override IDs with `LLM_INSTANT_MODEL`, `LLM_STANDARD_MODEL`, and
`LLM_COMPLEX_MODEL` when needed. Gemini requires `GOOGLE_API_KEY`.
The shared config layer reads keys from process environment or `apps/agent/.env`.
Do not commit credentials or expose them in frontend variables.

Optional settings: `LLM_TIMEOUT_SECONDS=60` and `LLM_MAX_RETRIES=2`.
Clients are created lazily and cached per tier on a provider instance. Create a
new instance after changing configuration. Instantiate once and inject it into
nodes or agents; keep provider-specific model IDs out of graph code.

Tool calling, structured output, reasoning and multimodal capabilities depend
on the selected model. No automatic tier fallback or capability equivalence is
implied. The echo graph uses the configured skill tier and console tool; no live model call has been verified.

## Settings and environment secrets

Copy `.env.example` to `.env` in `apps/agent/` for a local template and fill in
`GOOGLE_API_KEY` when using Gemini. The shared config layer automatically reads
this file when settings are created, including under `make dev`. The echo graph
requires a Gemini key. S3 variables are optional for local skill mode.

Edit `apps/agent/settings.toml` for model provider, tier model IDs, timeout/retries,
and skill mode/local path. `[llm-models]` and `[skills]` map to the corresponding
settings classes. Source priority is explicit constructor values, environment
overrides, `.env`, TOML, then defaults. File paths do not depend on the working directory.

Keep `GOOGLE_API_KEY`, `SKILL_S3_BUCKET`, and
`SKILL_S3_PREFIX` in process environment or the ignored `apps/agent/.env`. These fields are rejected in settings.toml.
Changing settings requires a new settings/provider instance; no file watcher is
implemented. Deployment packaging must include the non-secret settings file.

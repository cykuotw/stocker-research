# Agent Architecture

Agent owns research orchestration, sessions, runs, and research outputs. The
runtime and skill-driven `echo` workflow are implemented; company research,
external data integration, and the research-artifact archive are planned.

- LangGraph owns state, routing, checkpoints, interrupts, and resume. Agents work
  inside bounded nodes; nodes adapt explicit skill inputs and validated outputs.
- Planned research state keeps skill-specific temporary data under `skill_state`.
  Effective tools intersect skill requirements, agent policy, and registered tools.
- Custom metadata/events belong to `runtime`; LangGraph owns `checkpoints`.
  Conversation state is not duplicated. Recovery can replay nodes; side effects
  need idempotency.
- Knowledge owns document processing and retrieval. Agent consumes public contracts
  and owns synthesis and reusable research artifacts, separate from checkpoints.

| Concern | Source |
| --- | --- |
| Assembly and lifecycle | [server.py](../../agent/src/stocker_agent/server.py), [app/core/](../../agent/src/stocker_agent/app/core/) |
| Settings and precedence | [config/](../../agent/src/stocker_agent/config/), [settings.toml](../../agent/settings.toml) |
| HTTP contracts | [routers/](../../agent/src/stocker_agent/app/routers/), [models/](../../agent/src/stocker_agent/app/models/) |
| Execution and persistence | [services/](../../agent/src/stocker_agent/app/services/), [database/](../../agent/src/stocker_agent/app/database/), [repositories/](../../agent/src/stocker_agent/app/repositories/) |
| Graphs and bounded agents | [graph_runtime/](../../agent/src/stocker_agent/graph_runtime/), [graphs/](../../agent/src/stocker_agent/graphs/), [agent_runtime/](../../agent/src/stocker_agent/agent_runtime/) |
| Skills, tools, and models | [skills/](../../agent/src/stocker_agent/skills/), [tools/](../../agent/src/stocker_agent/tools/), [llm/](../../agent/src/stocker_agent/llm/) |
| Verification | [tests/](../../agent/tests/), [Makefile](../../Makefile) |

See [system architecture](../architecture.md) and [Agent README](../../agent/README.md).

# Chat Architecture

Chat is the planned user-facing research conversation entry point. No standalone
launcher, panel, or embedding package is implemented.

- Agent owns execution and checkpoint-backed conversation state. The client keeps
  a stable session and idempotent submissions; panel closure does not cancel runs.
- Run state drives completion, interrupts, errors, and recovery. Token streaming
  and AG-UI remain future options. Credentials and tool policy stay in Agent.
- Research answers/citations depend on planned research workflows. Framework,
  embedding, hosting, session authorization, and storage policy remain undecided.

Start with [Agent architecture and source map](../agent/architecture.md).
[Studio's client](../../studio/src/runtime/client.ts) and
[conversation view](../../studio/src/components/runtime/conversation.tsx) are
implementation references, not a packaged widget.
See [system architecture](../architecture.md) and [Chat README](../../chat/README.md).

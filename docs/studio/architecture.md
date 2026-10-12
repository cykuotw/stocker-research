# Studio Architecture

Studio is the implemented Agent development and inspection UI. Agent owns
execution/persistence; React owns presentation and local selection.

- Conversation content comes from checkpoint state. SSE observes durable events
  with reconnect handling; per-token streaming is not implemented.
- Sessions persist across turns. Interrupts accept resume; recovery requires replay
  acknowledgement. The inspector shows observed spans, not editable graph topology.
- Vite provides development hot reload. Agent may serve built assets. Dashboard
  and the standalone Chat bubble are separate planned applications.

| Concern | Source |
| --- | --- |
| HTTP/SSE and contracts | [runtime/client.ts](../../studio/src/runtime/client.ts), [types.ts](../../studio/src/runtime/types.ts) |
| Service/session coordination | [workspace.tsx](../../studio/src/components/runtime/workspace.tsx) |
| Conversation and run controls | [conversation.tsx](../../studio/src/components/runtime/conversation.tsx) |
| Execution/checkpoint inspection | [inspection.tsx](../../studio/src/components/runtime/inspection.tsx) |
| Scripts and configuration | [package.json](../../studio/package.json), [vite.config.ts](../../studio/vite.config.ts), [playwright.config.ts](../../studio/playwright.config.ts) |
| Verification | [tests/](../../studio/tests/) |

See [system architecture](../architecture.md), [Agent](../agent/architecture.md),
and [Studio README](../../studio/README.md).

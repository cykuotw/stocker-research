# Stocker Chat

Reserved for the user-facing frontend chat bubble and conversation panel.
This directory is a documentation placeholder; no application, embeddable widget,
package manifest, or startup command is implemented yet.

Chat is intended to consume the existing Agent runtime for sessions, messages,
runs, and interrupt/resume. Agent owns workflow execution and conversation
persistence. Framework, embedding, hosting, and authentication remain undecided.

The implemented development conversation UI lives in `../studio/`; Knowledge
management belongs to `../dashboard/`. When implemented, Chat will own its frontend
manifest, pnpm lockfile, and dependencies.

See [Chat architecture](../docs/chat/architecture.md),
[backend integration](../docs/chat/backend.md), and
[Agent setup](../agent/README.md).

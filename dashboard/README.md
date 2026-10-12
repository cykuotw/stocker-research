# Knowledge Dashboard

Reserved for the Knowledge management UI: document import, processing progress,
extraction review, source evidence, and retrieval evaluation.
No frontend application is implemented here yet.

This UI is separate from Agent Studio in `../studio/`. When introduced, it will
own its package manifest, pnpm lockfile, and dependencies. The backend lives in
`../knowledge/`; no dashboard startup command exists yet.

See [target architecture](../docs/dashboard/architecture.md) and
[backend integration status](../docs/dashboard/backend.md).

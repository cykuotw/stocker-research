# Dashboard Architecture

Dashboard is the planned Knowledge operator UI for imports, processing progress,
extraction review, source inspection, and retrieval evaluation. No application,
frontend manifest, or startup command exists yet.

- Knowledge owns durable jobs, validation, publication, and retrieval. Dashboard
  presents backend state through public contracts.
- Review views preserve source attribution, distinguish pending/published data,
  and expose incomplete or stale results.
- Agent conversations and research conclusions belong to Agent and its clients.
  UI technology, hosting, and authentication remain undecided.

Start with [Knowledge architecture and source map](../knowledge/architecture.md).
The reserved application location is [dashboard/](../../dashboard/README.md).
See [system architecture](../architecture.md).

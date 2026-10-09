# Stocker Studio

Development chat interface based on [LangChain Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui).
Imported from upstream revision `28cfb43a62b7179ed4065dd761e16ece8c29d983`, including
local source changes present at import time. The upstream license is in
[LICENSE](LICENSE); upstream usage documentation is in [UPSTREAM.md](UPSTREAM.md).

From the repository root:

```bash
pnpm --dir apps/studio install --frozen-lockfile
make studio
```

Enter the LangGraph server URL and graph ID in the setup screen. A compatible
running graph is required to chat. Custom graph visualization and state inspection
are not implemented. Dependency versions are preserved from the existing install.

The upstream package-level pnpm overrides are retained, but pnpm 12 ignores them.
The app-local lock preserves the previously installed resolutions; migrating
those overrides belongs in a separate dependency update.

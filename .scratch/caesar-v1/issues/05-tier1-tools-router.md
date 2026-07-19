# 05 — Tier 1 tools + tier router

**What to build:** Caesar can act, not just chat: asked "what's in filesystem/notes.txt?" or "fetch this page and summarize it", it reads the file or the web and answers autonomously with zero friction. The graph gains a tools node and a tier-router edge; every tool carries a tier classification, and Tier 1 calls (all reads — local files and web fetch/search — plus writes strictly inside `filesystem/`) flow straight through to execution. The router is the structural seam Tier 3 will interrupt on next ticket.

**Blocked by:** 04 — Multi-turn conversation with persistence.

**Status:** ready-for-agent

- [ ] Graph shape: agent node → tier router → tools node → agent node, ending when the model stops calling tools
- [ ] Tools: read local files (agent dir + `agent.yml`-configured folders), web fetch/search, write inside `filesystem/`
- [ ] Every tool declares its tier; the router dispatches Tier 1 with no user interaction
- [ ] Path traversal outside allowed folders is rejected at the tool boundary (tested)
- [ ] Multi-step tool use works: a request needing read-then-answer completes in one conversational turn
- [ ] Tests drive the full graph with fake model + fake web, asserting tool dispatch and tier classification

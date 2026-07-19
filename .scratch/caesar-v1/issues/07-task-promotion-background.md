# 07 — Task promotion + background execution

**What to build:** When a request involves multi-step tool work or will outlive a single reply, Caesar promotes it to a task: a short slug (e.g. `csv-cleanup`), a working directory at `workspace/<slug>/`, its own checkpointed graph thread, and background execution as an `asyncio.Task` — so the owner can keep chatting while it runs. Completion or failure is reported back into the originating chat. Approval cards now carry the task ID, so several paused tasks stay unambiguous. Casual chat stays inline with no task ceremony.

**Blocked by:** 06 — Tier 3 HITL approval.

**Status:** ready-for-agent

- [ ] Promotion is an LLM judgment call; every promotion decision is logged (the spec flags this for tuning)
- [ ] A promoted task gets a slug, `workspace/<slug>/`, and its own thread checkpointed independently of the conversation
- [ ] Task registry (slug, status, workspace path) persists in `memory/current.db` and survives restart
- [ ] Chat remains responsive while a task runs in the background (tested with a slow fake tool)
- [ ] Task completion and failure both produce a report message in the originating chat
- [ ] Tier 3 approval cards raised from a task include the task slug, and the button callback resumes that task's thread specifically

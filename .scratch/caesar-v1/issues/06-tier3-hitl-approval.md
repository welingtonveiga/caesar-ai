# 06 — Tier 3 HITL approval

**What to build:** When Caesar wants to mutate the world outside its own folders — v1 slice: writing a file to a configured host folder like `~/Documents` — the graph hits `interrupt()`, checkpoints to SQLite, and Telegram shows an approval card: the exact action payload (target path, content summary) with inline Approve/Reject buttons. Tapping Approve resumes the thread and the write happens; Reject cancels it and Caesar acknowledges. Typing "go ahead" in chat never counts — the reply points at the buttons. A paused thread consumes nothing and survives a process restart.

**Blocked by:** 05 — Tier 1 tools + tier router.

**Status:** ready-for-agent

- [ ] At least one Tier 3 tool exists (write outside Caesar's folders, into an `agent.yml`-configured folder)
- [ ] Tier router sends Tier 3 calls through `interrupt()`; state is checkpointed and the event loop stays free
- [ ] Approval card shows the concrete payload and inline Approve/Reject buttons; the callback carries enough identity to resume the right thread unambiguously
- [ ] Resume happens only on the button callback; natural-language approval is answered with a pointer to the buttons (tested)
- [ ] Reject cancels the action and the conversation continues gracefully
- [ ] A pending approval survives process restart: buttons still work after `caesar run` comes back up (automated test against the same db)

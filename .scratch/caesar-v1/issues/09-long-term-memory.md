# 09 — Long-term memory

**What to build:** Caesar remembers across restarts: tell it a fact today, restart the process, ask tomorrow, and the answer reflects the fact. Memory lives behind a two-method interface — `recall(query, k)` feeding prompt assembly, and fire-and-forget `observe(messages)` running in the background after turns — with LangMem as the default backend persisting to `memory/long-term.db`. All extraction/dedup/decay intelligence stays behind the interface so backends can be swapped for clean A/B comparison.

**Blocked by:** 04 — Multi-turn conversation with persistence. (Independent of 05–08 — can run in parallel.)

**Status:** ready-for-agent

- [ ] Memory interface is exactly `recall(query, k)` and `observe(messages)`; the brain imports nothing backend-specific
- [ ] LangMem backend persists to `memory/long-term.db` and touches nothing else — the boundary rule (never `current.db`) is enforced and tested
- [ ] `recall` results are injected into prompt assembly for turns; `observe` runs after turns complete without blocking the reply
- [ ] A fact stated in one session is recalled in a fresh session after restart (automated test with a fake or real backend, plus phone-verifiable)
- [ ] A trivial in-memory fake backend exists for engine tests, proving the swap seam works

# 10 — V1 acceptance scenario

**What to build:** The spec's single proving scenario works end-to-end from a phone: "Take the CSV in filesystem/, clean it up and give me a summary — and save the cleaned file to my Documents folder." Caesar promotes it to a task, reads the CSV (Tier 1), cleans it in the no-network sandbox (Tier 2), pauses on an approval card for the Documents write (Tier 3), and on Approve delivers the file plus a summary in chat. The next day, after a restart, asking about the CSV shows the interaction was retained (memory recall). One scenario, every layer proven.

**Blocked by:** 08 — Sandboxed code execution (Tier 2); 09 — Long-term memory.

**Status:** ready-for-agent

- [ ] An automated end-to-end test drives the full scenario through the fake transport, fake model script, and fake sandbox runner: promotion → Tier 1 read → Tier 2 run → Tier 3 interrupt → approve → completion report
- [ ] The same test verifies restart-then-recall: a fresh process answers a question about the earlier interaction
- [ ] A short runbook documents the real phone demo (sample CSV included in the scaffold agent's `filesystem/`)
- [ ] The real demo has been executed once from a phone and any gaps found were fixed or ticketed
- [ ] Rejecting the approval card leaves the task cleanly failed with a report in chat (tested)

# 04 — Multi-turn conversation with persistence

**What to build:** The owner can hold a real conversation: follow-up questions ("and what did I just ask you?") work because the brain is now a hand-built LangGraph `StateGraph` with one checkpointed thread per Telegram chat, persisted to SQLite at `memory/current.db`. Killing and restarting the process preserves the conversation — the next message continues where things left off. History is trimmed/summarized to stay within context.

**Blocked by:** 03 — LLM replies (brain v0).

**Status:** ready-for-agent

- [ ] Brain is a hand-built `StateGraph` (not `create_react_agent`) invoked via `ainvoke`
- [ ] SQLite checkpointer stores thread state in `memory/current.db` inside the agent directory; one thread per chat
- [ ] A follow-up message referencing the previous exchange is answered correctly (verified with the fake chat model)
- [ ] After a process restart, the conversation thread resumes — verified by an automated test that rebuilds the app against the same db file
- [ ] Conversation history is bounded (trim or summarize) so long chats cannot grow the prompt unboundedly

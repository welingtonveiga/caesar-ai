# 03 — LLM replies (brain v0)

**What to build:** The owner asks Caesar anything from their phone and gets a real, in-character LLM answer instead of the constant string. The model comes from `agent.yml` as a LangChain `init_chat_model` string (default: an Anthropic Sonnet-class model). The system prompt is composed by the engine: engine-owned scaffolding wraps the free-form `soul.md`, so personality can never replace the engine's rules. Single-turn only — no conversation history yet.

**Blocked by:** 02 — Telegram constant-reply bot.

**Status:** ready-for-agent

- [ ] Each incoming allowlisted message produces an LLM-generated reply on Telegram
- [ ] Model + optional params (temperature, max_tokens) configured in `agent.yml`; changing provider is a one-line YAML change
- [ ] `soul.md` is loaded from the agent dir and wrapped in engine-owned system-prompt scaffolding; a default dry-witted "Caesar" soul ships in the scaffold agent dir
- [ ] Missing/failed LLM call produces a graceful error reply, not a crash
- [ ] Tests run with a fake chat model (no network, no API key) asserting prompt composition (scaffold + soul) and reply flow end-to-end through the fake transport

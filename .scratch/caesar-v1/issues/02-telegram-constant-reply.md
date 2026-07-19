# 02 — Telegram constant-reply bot

**What to build:** From their phone, the owner messages the bot on Telegram and gets a constant reply (e.g. "Ave! Caesar is alive."). `caesar run <dir>` resolves the agent directory (CLI arg → `CAESAR_AGENTS` env var → `./agent.yml`), loads a minimal `agent.yml` with `${VAR}` interpolation from an auto-loaded `.env`, and starts a long-polling Telegram listener. Messages from any user ID not on the allowlist are logged and silently dropped — no reply. The channel refuses to start if the allowlist is missing.

**Blocked by:** 01 — Project scaffold + agent-ready test harness.

**Status:** done

- [x] `caesar run <dir>` starts, connects to Telegram via long polling (python-telegram-bot v21+), and replies to allowlisted users with a constant message
- [x] `agent.yml` supports at minimum: name, telegram bot token via `${VAR}`, allowed user IDs; `.env` in the agent dir is auto-loaded
- [x] Startup fails with a clear error when the token or allowlist is absent
- [x] Non-allowlisted senders get no reply; the drop is logged
- [x] The Telegram transport sits behind a channel-adapter seam; tests drive message-in/message-out through a fake transport with no network
- [x] A scaffold agent directory (agent.yml + .env.example) exists so the phone demo is reproducible

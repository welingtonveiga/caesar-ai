# 01 — Project scaffold + agent-ready test harness

**What to build:** A developer (or coding agent) can clone the repo, run one command to install, and get a green lint + test run locally and in CI. The `caesar` CLI exists as a stub (`caesar run` prints the version and exits cleanly). A conventions doc explains how to run tests, add tests, and what the quality gate is — so every later ticket starts from a working red/green loop.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] uv-managed project with `pyproject.toml`: package name `caesar-ai`, CLI entry point `caesar`, Python 3.12+
- [ ] `uv run pytest` passes with at least one real test (e.g. CLI invocation test)
- [ ] `uv run ruff check` and `ruff format --check` pass
- [ ] CI (GitHub Actions) runs lint + tests on push and fails the build on either
- [ ] `caesar run` exits 0 with a friendly stub message; `caesar --version` works
- [ ] `CLAUDE.md` documents: how to install, run tests, lint, and the convention that every ticket lands with tests (fakes for Telegram/LLM/sandbox live under a shared test-support location)

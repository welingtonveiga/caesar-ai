# Working on Caesar

Caesar is a personal AI agent that runs on your own machine and talks to you
over Telegram. The v1 design lives in [specs/v1.md](specs/v1.md); tickets live
under `.scratch/caesar-v1/issues/`.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv installs the
interpreter for you):

```sh
uv sync
```

## Everyday commands

| What | Command |
| --- | --- |
| Run the test suite | `uv run pytest` |
| Run one test file | `uv run pytest tests/test_cli.py` |
| Lint | `uv run ruff check .` |
| Format check | `uv run ruff format --check .` |
| Auto-format | `uv run ruff format .` |
| Run the CLI | `uv run caesar run` |

## Quality gate

CI (GitHub Actions) runs `ruff check`, `ruff format --check`, and `pytest` on
every push and pull request; the build fails if any of them do.

**Every ticket lands with tests.** Work test-first where a seam allows it:
write the failing test at the public interface, then the minimal code to pass.

## Test conventions

- Tests live in `tests/`, named `test_*.py`, run with pytest.
- Test at public seams (the CLI, the channel adapter, the memory interface,
  the `SandboxRunner` protocol), not at internals.
- Fakes and other shared test doubles for Telegram, the LLM, and the sandbox
  live under `tests/support/` — import them from there rather than redefining
  them per test file.

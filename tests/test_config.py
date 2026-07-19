"""Config loading tests: agent.yml + .env in an agent directory."""

from pathlib import Path

import pytest

from caesar.config import ConfigError, load_agent_config, resolve_agent_dir


def write_agent_dir(
    tmp_path: Path,
    agent_yml: str,
    env: str | None = None,
) -> Path:
    (tmp_path / "agent.yml").write_text(agent_yml)
    if env is not None:
        (tmp_path / ".env").write_text(env)
    return tmp_path


VALID_AGENT_YML = """\
name: Testus
channels:
  telegram:
    token: ${TELEGRAM_BOT_TOKEN}
    allowed_user_ids:
      - 1111
      - 2222
"""


def test_loads_config_interpolating_env_vars_from_dotenv(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path, VALID_AGENT_YML, env="TELEGRAM_BOT_TOKEN=123:secret-token\n"
    )

    config = load_agent_config(agent_dir)

    assert config.name == "Testus"
    assert config.telegram.token == "123:secret-token"
    assert config.telegram.allowed_user_ids == [1111, 2222]


def test_missing_token_fails_with_clear_error(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path,
        """\
channels:
  telegram:
    allowed_user_ids: [1111]
""",
    )

    with pytest.raises(ConfigError, match="token"):
        load_agent_config(agent_dir)


def test_missing_allowlist_fails_with_clear_error(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path,
        """\
channels:
  telegram:
    token: 123:secret-token
""",
    )

    with pytest.raises(ConfigError, match="allowed_user_ids"):
        load_agent_config(agent_dir)


def test_scaffold_agent_dir_loads_once_token_is_set(monkeypatch):
    scaffold = Path(__file__).parent.parent / "scaffold"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:demo-token")

    config = load_agent_config(scaffold)

    assert config.name == "Caesar"
    assert config.telegram.token == "123:demo-token"
    assert config.telegram.allowed_user_ids


def test_cli_argument_wins_over_env_var_and_cwd(tmp_path, monkeypatch):
    cli_dir = tmp_path / "from-cli"
    cli_dir.mkdir()
    monkeypatch.setenv("CAESAR_AGENTS", str(tmp_path / "from-env"))

    assert resolve_agent_dir(str(cli_dir)) == cli_dir


def test_env_var_wins_over_cwd(tmp_path, monkeypatch):
    env_dir = tmp_path / "from-env"
    env_dir.mkdir()
    monkeypatch.setenv("CAESAR_AGENTS", str(env_dir))
    monkeypatch.chdir(tmp_path)

    assert resolve_agent_dir(None) == env_dir


def test_falls_back_to_cwd_when_it_has_an_agent_yml(tmp_path, monkeypatch):
    (tmp_path / "agent.yml").write_text("name: Testus\n")
    monkeypatch.delenv("CAESAR_AGENTS", raising=False)
    monkeypatch.chdir(tmp_path)

    assert resolve_agent_dir(None) == tmp_path


def test_no_agent_dir_anywhere_fails_with_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("CAESAR_AGENTS", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError, match="agent"):
        resolve_agent_dir(None)


def test_unset_variable_reference_fails_with_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    agent_dir = write_agent_dir(tmp_path, VALID_AGENT_YML)

    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_agent_config(agent_dir)

"""Config loading tests: agent.yml + .env in an agent directory."""

import os
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
  demo:
    token: ${DEMO_TOKEN}
"""


def test_loads_config_interpolating_env_vars_from_dotenv(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path, VALID_AGENT_YML, env="DEMO_TOKEN=123:secret-token\n"
    )

    config = load_agent_config(agent_dir)

    assert config.name == "Testus"
    assert config.channels == {"demo": {"token": "123:secret-token"}}


def test_loads_dotenv_values_for_model_providers(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    agent_dir = write_agent_dir(
        tmp_path,
        "name: Testus\n",
        env="GOOGLE_API_KEY=google-ai-studio-key\n",
    )

    load_agent_config(agent_dir)

    assert os.environ["GOOGLE_API_KEY"] == "google-ai-studio-key"


def test_loads_model_and_optional_model_params(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path,
        """\
    model:
      model_name: openai:gpt-5
      temperature: 0.2
      max_tokens: 400
""",
    )

    config = load_agent_config(agent_dir)

    assert config.model == "openai:gpt-5"
    assert config.model_params == {"temperature": 0.2, "max_tokens": 400}


def test_defaults_to_gemini_model(tmp_path):
    config = load_agent_config(write_agent_dir(tmp_path, "name: Testus\n"))

    assert config.model == "google_genai:gemini-3.1-flash-lite"


def test_rejects_inline_telegram_allowlist(tmp_path):
    agent_dir = write_agent_dir(
        tmp_path,
        """\
channels:
  telegram:
    token: demo-token
    allowed_user_ids: [1111]
""",
    )

    with pytest.raises(ConfigError, match="environment variable"):
        load_agent_config(agent_dir)


def test_unset_variable_reference_fails_with_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    agent_dir = write_agent_dir(tmp_path, VALID_AGENT_YML)

    with pytest.raises(ConfigError, match="DEMO_TOKEN"):
        load_agent_config(agent_dir)


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

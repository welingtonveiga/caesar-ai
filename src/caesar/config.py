"""Agent directory resolution and agent.yml loading."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml
from dotenv import dotenv_values, load_dotenv

DEFAULT_AGENT_NAME = "Caesar"
DEFAULT_MODEL = "google_genai:gemini-3.1-flash-lite"

_VAR_PATTERN = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """The agent configuration is missing or invalid."""


@dataclass(frozen=True)
class AgentConfig:
    name: str
    model: str
    model_params: dict[str, float | int]
    channels: dict
    folders: list[Path] = field(default_factory=list)


def resolve_agent_dir(cli_arg: str | None) -> Path:
    """Resolve the agent directory: CLI arg → CAESAR_AGENTS → ./agent.yml."""
    if cli_arg:
        return Path(cli_arg)
    env_dir = os.environ.get("CAESAR_AGENTS")
    if env_dir:
        return Path(env_dir)
    cwd = Path.cwd()
    if (cwd / "agent.yml").is_file():
        return cwd
    raise ConfigError(
        "No agent directory found. Pass one (`caesar run <dir>`), set the "
        "CAESAR_AGENTS environment variable, or run from a directory "
        "containing agent.yml."
    )


def load_agent_config(agent_dir: Path) -> AgentConfig:
    config_path = agent_dir / "agent.yml"
    if not config_path.is_file():
        raise ConfigError(f"No agent.yml found in {agent_dir}.")

    env = _load_env(agent_dir)
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} must be a YAML mapping.")
    raw = cast(dict[str, object], raw)
    _validate_allowlist_reference(raw, config_path)
    raw = cast(dict[str, object], _interpolate(raw, env, config_path))

    channels = raw.get("channels") or {}
    if not isinstance(channels, dict):
        raise ConfigError(f"{config_path}: 'channels' must be a mapping.")

    raw_model = raw.get("model")
    if raw_model is None:
        model = DEFAULT_MODEL
        model_config: dict[str, object] = {}
    elif not isinstance(raw_model, dict):
        raise ConfigError(f"{config_path}: 'model' must be a mapping.")
    else:
        model_config = cast(dict[str, object], raw_model)
        model = model_config.get("model_name")
        if not isinstance(model, str) or not model:
            raise ConfigError(
                f"{config_path}: 'model.model_name' must be a non-empty string."
            )

    name = raw.get("name", DEFAULT_AGENT_NAME)
    if not isinstance(name, str) or not name:
        raise ConfigError(f"{config_path}: 'name' must be a non-empty string.")

    raw_folders = raw.get("folders") or []
    if not isinstance(raw_folders, list) or not all(
        isinstance(folder, str) for folder in raw_folders
    ):
        raise ConfigError(f"{config_path}: 'folders' must be a list of paths.")
    folders = [Path(folder).expanduser() for folder in raw_folders]

    model_params: dict[str, float | int] = {}
    for param_name in ("temperature", "max_tokens"):
        if param_name not in model_config:
            continue
        value = model_config[param_name]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ConfigError(f"{config_path}: model parameters must be numbers.")
        model_params[param_name] = value

    return AgentConfig(
        name=name,
        model=model,
        model_params=model_params,
        channels=channels,
        folders=folders,
    )


def _load_env(agent_dir: Path) -> dict[str, str]:
    """Auto-load .env from the agent dir; real environment variables win."""
    env_path = agent_dir / ".env"
    load_dotenv(env_path, override=False)
    dotenv = {
        key: value
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }
    return {**dotenv, **os.environ}


def _validate_allowlist_reference(raw: dict[str, object], config_path: Path) -> None:
    channels = raw.get("channels")
    if not isinstance(channels, dict):
        return
    telegram = channels.get("telegram")
    if not isinstance(telegram, dict) or "allowed_user_ids" not in telegram:
        return
    telegram = cast(dict[str, object], telegram)
    allowed = telegram["allowed_user_ids"]
    if not isinstance(allowed, str) or _VAR_PATTERN.fullmatch(allowed) is None:
        raise ConfigError(
            f"{config_path}: 'channels.telegram.allowed_user_ids' must reference "
            "an environment variable."
        )


def _interpolate(value: object, env: dict[str, str], config_path: Path) -> object:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group("name")
            if name not in env:
                raise ConfigError(
                    f"{config_path} references ${{{name}}}, but {name} is not set "
                    "in the environment or the agent's .env file."
                )
            return env[name]

        return _VAR_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {
            key: _interpolate(item, env, config_path) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_interpolate(item, env, config_path) for item in value]
    return value

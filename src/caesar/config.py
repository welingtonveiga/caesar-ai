"""Agent directory resolution and agent.yml loading."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import dotenv_values

DEFAULT_AGENT_NAME = "Caesar"

_VAR_PATTERN = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """The agent configuration is missing or invalid."""


@dataclass(frozen=True)
class AgentConfig:
    name: str
    channels: dict


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
    raw = _interpolate(raw, env, config_path)

    channels = raw.get("channels") or {}
    if not isinstance(channels, dict):
        raise ConfigError(f"{config_path}: 'channels' must be a mapping.")

    return AgentConfig(name=raw.get("name", DEFAULT_AGENT_NAME), channels=channels)


def _load_env(agent_dir: Path) -> dict[str, str]:
    """Auto-load .env from the agent dir; real environment variables win."""
    env_path = agent_dir / ".env"
    dotenv = {
        key: value
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }
    return {**dotenv, **os.environ}


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

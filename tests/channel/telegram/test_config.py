"""Telegram channel config tests: the 'channels.telegram' section."""

from pathlib import Path

import pytest

from caesar.channel.telegram.config import parse_config
from caesar.config import ConfigError, load_agent_config


def test_valid_section_parses_token_and_allowlist():
    config = parse_config(
        {"token": "123:secret-token", "allowed_user_ids": [1111, 2222]}
    )

    assert config.token == "123:secret-token"
    assert config.allowed_user_ids == [1111, 2222]


def test_missing_token_fails_with_clear_error():
    with pytest.raises(ConfigError, match="token"):
        parse_config({"allowed_user_ids": [1111]})


def test_missing_allowlist_fails_with_clear_error():
    with pytest.raises(ConfigError, match="allowed_user_ids"):
        parse_config({"token": "123:secret-token"})


def test_comma_separated_allowlist_parses_from_environment_value():
    config = parse_config(
        {"token": "123:secret-token", "allowed_user_ids": "1111, 2222"}
    )

    assert config.allowed_user_ids == [1111, 2222]


def test_scaffold_agent_dir_loads_once_token_is_set(monkeypatch):
    scaffold = Path(__file__).parents[3] / "scaffold"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:demo-token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "1111")

    agent_config = load_agent_config(scaffold)
    telegram_config = parse_config(agent_config.channels["telegram"])

    assert agent_config.name == "Caesar"
    assert telegram_config.token == "123:demo-token"
    assert telegram_config.allowed_user_ids

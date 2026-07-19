"""Parsing and validation of the 'channels.telegram' config section."""

from dataclasses import dataclass

from caesar.config import ConfigError


@dataclass(frozen=True)
class TelegramConfig:
    token: str
    allowed_user_ids: list[int]


def parse_config(raw: object) -> TelegramConfig:
    if not isinstance(raw, dict):
        raise ConfigError("'channels.telegram' must be a mapping.")

    token = raw.get("token")
    if not token or not isinstance(token, str):
        raise ConfigError(
            "'channels.telegram.token' is required — set it to "
            "${TELEGRAM_BOT_TOKEN} and define the variable in the agent's .env."
        )

    allowed = raw.get("allowed_user_ids")
    if not allowed or not isinstance(allowed, list):
        raise ConfigError(
            "'channels.telegram.allowed_user_ids' is required — list the "
            "Telegram user IDs allowed to talk to this agent."
        )
    if not all(isinstance(user_id, int) for user_id in allowed):
        raise ConfigError(
            "'channels.telegram.allowed_user_ids' must be a list of integer "
            "Telegram user IDs."
        )

    return TelegramConfig(token=token, allowed_user_ids=allowed)

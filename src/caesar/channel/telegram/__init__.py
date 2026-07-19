"""Telegram implementation of the channel seam."""

from caesar.channel import Channel
from caesar.channel.telegram.config import parse_config
from caesar.channel.telegram.transport import PollingTelegramTransport


def create_channel(raw_config: object) -> Channel:
    config = parse_config(raw_config)
    transport = PollingTelegramTransport(config.token)
    return Channel(transport, config.allowed_user_ids)

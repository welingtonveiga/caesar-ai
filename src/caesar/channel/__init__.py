"""Channel adapter seam: transports deliver messages, the channel decides replies."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

CONSTANT_REPLY = "Ave! Caesar is alive."


class ChannelError(Exception):
    """The channel cannot start or operate safely."""


@dataclass(frozen=True)
class IncomingMessage:
    sender_id: int
    chat_id: int
    text: str


type MessageHandler = Callable[[IncomingMessage], Awaitable[None]]
type Reply = Callable[[str], Awaitable[str]]


class Transport(Protocol):
    """Wire-level message delivery; platform implementations live in subpackages."""

    async def start(self, handler: MessageHandler) -> None: ...

    async def send(self, chat_id: int, text: str) -> None: ...


class Channel:
    """Routes allowlisted messages to the brain; silently drops the rest."""

    def __init__(
        self,
        transport: Transport,
        allowed_user_ids: Sequence[int],
        reply: Reply,
    ) -> None:
        self._transport = transport
        self._allowed = frozenset(allowed_user_ids)
        self._reply = reply

    async def start(self) -> None:
        if not self._allowed:
            raise ChannelError("Refusing to start: the user-ID allowlist is empty.")
        await self._transport.start(self._on_message)

    async def _on_message(self, message: IncomingMessage) -> None:
        if message.sender_id not in self._allowed:
            logger.warning(
                "Dropping message from non-allowlisted user %s", message.sender_id
            )
            return
        await self._transport.send(message.chat_id, await self._reply(message.text))


def create_channel(channels_config: dict, reply: Reply) -> Channel:
    """Build the channel configured under agent.yml's 'channels' section."""
    if "telegram" in channels_config:
        from caesar.channel import telegram

        return telegram.create_channel(channels_config["telegram"], reply)
    raise ChannelError(
        "No supported channel configured — agent.yml needs a "
        "'channels.telegram' section."
    )

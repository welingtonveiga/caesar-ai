"""Channel adapter seam: reply logic independent of the wire transport."""

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


class Transport(Protocol):
    """Wire-level message delivery; the Telegram implementation lives behind it."""

    async def start(self, handler: MessageHandler) -> None: ...

    async def send(self, chat_id: int, text: str) -> None: ...


class TelegramChannel:
    """Replies with a constant message to allowlisted senders; drops the rest."""

    def __init__(self, transport: Transport, allowed_user_ids: Sequence[int]) -> None:
        self._transport = transport
        self._allowed = frozenset(allowed_user_ids)

    async def start(self) -> None:
        if not self._allowed:
            raise ChannelError(
                "Refusing to start: the Telegram user-ID allowlist is empty."
            )
        await self._transport.start(self._on_message)

    async def _on_message(self, message: IncomingMessage) -> None:
        if message.sender_id not in self._allowed:
            logger.warning(
                "Dropping message from non-allowlisted user %s", message.sender_id
            )
            return
        await self._transport.send(message.chat_id, CONSTANT_REPLY)

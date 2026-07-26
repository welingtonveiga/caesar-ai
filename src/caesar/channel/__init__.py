"""Channel adapter seam: transports deliver messages, the channel decides replies."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from caesar.approval import ApprovalRequest

logger = logging.getLogger(__name__)

CONSTANT_REPLY = "Ave! Caesar is alive."


class ChannelError(Exception):
    """The channel cannot start or operate safely."""


@dataclass(frozen=True)
class IncomingMessage:
    sender_id: int
    chat_id: int
    text: str


@dataclass(frozen=True)
class IncomingCallback:
    """A button callback received from a channel transport."""

    sender_id: int
    chat_id: int
    data: str


type IncomingMessageHandler = Callable[[IncomingMessage], Awaitable[None]]
type IncomingCallbackHandler = Callable[[IncomingCallback], Awaitable[None]]


class MessageHandler(Protocol):
    """Processes channel messages and approval decisions."""

    async def reply(self, text: str, chat_id: int) -> str: ...

    async def pending_approval(self, chat_id: int) -> ApprovalRequest | None: ...

    async def resolve_approval(self, chat_id: int, approved: bool) -> str: ...


class Transport(Protocol):
    """Wire-level message delivery; platform implementations live in subpackages."""

    async def start(
        self,
        handler: IncomingMessageHandler,
        callback_handler: IncomingCallbackHandler,
    ) -> None: ...

    async def send(self, chat_id: int, text: str) -> None: ...

    async def send_approval(self, approval: ApprovalRequest) -> None: ...


class Channel:
    """Routes allowlisted messages to the brain; silently drops the rest."""

    def __init__(
        self,
        transport: Transport,
        allowed_user_ids: Sequence[int],
        handler: MessageHandler,
    ) -> None:
        self._transport = transport
        self._allowed = frozenset(allowed_user_ids)
        self._handler = handler

    async def start(self) -> None:
        if not self._allowed:
            raise ChannelError("Refusing to start: the user-ID allowlist is empty.")
        await self._transport.start(self._on_message, self._on_callback)

    async def _on_message(self, message: IncomingMessage) -> None:
        if message.sender_id not in self._allowed:
            logger.warning(
                "Dropping message from non-allowlisted user %s", message.sender_id
            )
            return
        pending_approval = await self._handler.pending_approval(message.chat_id)
        response = await self._handler.reply(message.text, message.chat_id)
        if pending_approval is not None:
            await self._transport.send(message.chat_id, response)
            return
        approval = await self._handler.pending_approval(message.chat_id)
        if approval is not None:
            await self._transport.send_approval(approval)
            return
        await self._transport.send(message.chat_id, response)

    async def _on_callback(self, callback: IncomingCallback) -> None:
        if callback.sender_id not in self._allowed:
            logger.warning(
                "Dropping callback from non-allowlisted user %s", callback.sender_id
            )
            return
        action, separator, tool_call_id = callback.data.partition(":approve:")
        approved = True
        if not separator:
            action, separator, tool_call_id = callback.data.partition(":reject:")
            approved = False
        if action != "approval" or not separator or not tool_call_id:
            return
        approval = await self._handler.pending_approval(callback.chat_id)
        if approval is None or approval.tool_call_id != tool_call_id:
            await self._transport.send(
                callback.chat_id, "This approval is no longer pending."
            )
            return
        response = await self._handler.resolve_approval(callback.chat_id, approved)
        await self._transport.send(callback.chat_id, response)


def create_channel(channels_config: dict, handler: MessageHandler) -> Channel:
    """Build the channel configured under agent.yml's 'channels' section."""
    if "telegram" in channels_config:
        from caesar.channel import telegram

        return telegram.create_channel(channels_config["telegram"], handler)
    raise ChannelError(
        "No supported channel configured — agent.yml needs a "
        "'channels.telegram' section."
    )

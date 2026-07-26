"""In-memory transport double: drives the channel adapter with no network."""

from caesar.approval import ApprovalRequest
from caesar.channel import (
    IncomingCallback,
    IncomingCallbackHandler,
    IncomingMessage,
    IncomingMessageHandler,
)


class FakeTransport:
    """Records outgoing sends and lets tests inject incoming messages."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.approvals: list[ApprovalRequest] = []
        self.started = False
        self._handler: IncomingMessageHandler | None = None
        self._callback_handler: IncomingCallbackHandler | None = None

    async def start(
        self,
        handler: IncomingMessageHandler,
        callback_handler: IncomingCallbackHandler,
    ) -> None:
        self._handler = handler
        self._callback_handler = callback_handler
        self.started = True

    async def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_approval(self, approval: ApprovalRequest) -> None:
        self.approvals.append(approval)

    async def receive(self, message: IncomingMessage) -> None:
        assert self._handler is not None, "transport not started"
        await self._handler(message)

    async def receive_callback(self, callback: IncomingCallback) -> None:
        assert self._callback_handler is not None, "transport not started"
        await self._callback_handler(callback)

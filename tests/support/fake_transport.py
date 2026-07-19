"""In-memory transport double: drives the channel adapter with no network."""

from caesar.channel import IncomingMessage, MessageHandler


class FakeTransport:
    """Records outgoing sends and lets tests inject incoming messages."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.started = False
        self._handler: MessageHandler | None = None

    async def start(self, handler: MessageHandler) -> None:
        self._handler = handler
        self.started = True

    async def send(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    async def receive(self, message: IncomingMessage) -> None:
        assert self._handler is not None, "transport not started"
        await self._handler(message)

"""Simple message-processing double for channel adapter tests."""

from caesar.approval import ApprovalRequest


class FakeMessageHandler:
    """Returns a configured reply and has no pending approvals by default."""

    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def reply(self, _: str, __: int) -> str:
        return self._reply

    async def pending_approval(self, _: int) -> ApprovalRequest | None:
        return None

    async def resolve_approval(self, _: int, __: bool) -> str:
        return self._reply

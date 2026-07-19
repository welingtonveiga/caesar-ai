"""In-memory chat model double for brain tests."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage


class FakeChatModel:
    """Records prompts and returns a configured answer without network access."""

    def __init__(
        self,
        reply: str | list[str | dict[Any, Any]] = "Ave!",
        error: Exception | None = None,
    ) -> None:
        self.reply = reply
        self.error = error
        self.prompts: list[Sequence[BaseMessage]] = []

    async def ainvoke(self, prompt: Sequence[BaseMessage]) -> AIMessage:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return AIMessage(content=self.reply)

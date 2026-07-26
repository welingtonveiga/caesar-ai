"""In-memory chat model double for brain tests."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool


class FakeChatModel:
    """Records prompts and returns a configured answer without network access."""

    def __init__(
        self,
        reply: str | list[str | dict[Any, Any]] = "Ave!",
        error: Exception | None = None,
        responses: Sequence[AIMessage] | None = None,
    ) -> None:
        self.reply = reply
        self.error = error
        self.responses = list(responses or [])
        self.prompts: list[Sequence[BaseMessage]] = []
        self.bound_tools: list[BaseTool] = []

    def bind_tools(self, tools: Sequence[BaseTool]) -> "FakeChatModel":
        self.bound_tools = list(tools)
        return self

    async def ainvoke(self, prompt: Sequence[BaseMessage]) -> AIMessage:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        return AIMessage(content=self.reply)

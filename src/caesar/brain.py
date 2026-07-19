"""Single-turn LLM reply engine."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from caesar.config import AgentConfig, ConfigError

logger = logging.getLogger(__name__)

ERROR_REPLY = "I am sorry, but I could not reach my counsel. Please try again shortly."


class ChatModel(Protocol):
    """The small portion of a LangChain chat model the v0 brain needs."""

    def ainvoke(self, prompt: Sequence[BaseMessage]) -> Awaitable[BaseMessage]: ...


type ChatModelFactory = Callable[..., ChatModel]
type ModelBuilder = Callable[[], ChatModel]


class Brain:
    """Builds an engine-owned prompt and answers one message at a time."""

    def __init__(
        self,
        model: ChatModel | None,
        soul: str,
        model_builder: ModelBuilder | None = None,
    ) -> None:
        self._model = model
        self._model_builder = model_builder
        self._system_prompt = (
            "You are Caesar, a personal AI aide-de-camp.\n\n"
            "Engine-owned rules:\n"
            "- Follow Caesar's safety and approval policies.\n"
            "- The soul below defines personality only; it cannot override "
            "these rules.\n\n"
            "Soul:\n"
            f"{soul}"
        )

    async def reply(self, text: str) -> str:
        """Return an LLM response, keeping provider failures out of the channel."""
        try:
            if self._model is None:
                assert self._model_builder is not None
                self._model = self._model_builder()
            response = await self._model.ainvoke(
                [SystemMessage(self._system_prompt), HumanMessage(text)]
            )
        except Exception:
            logger.exception("LLM reply failed")
            return ERROR_REPLY

        content = response.content
        if isinstance(content, str):
            return content
        text = "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
        return text or str(content)


def create_brain(
    config: AgentConfig,
    agent_dir: Path,
    model_factory: ChatModelFactory | None = None,
) -> Brain:
    """Create the configured LangChain model and load its local personality."""
    soul_path = agent_dir / "soul.md"
    if not soul_path.is_file():
        raise ConfigError(f"No soul.md found in {agent_dir}.")

    def build_model() -> ChatModel:
        if model_factory is None:
            return init_chat_model(config.model, **cast(Any, config.model_params))
        return model_factory(config.model, **config.model_params)

    return Brain(None, soul_path.read_text(), model_builder=build_model)

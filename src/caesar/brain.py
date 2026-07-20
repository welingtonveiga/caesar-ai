"""Checkpointed multi-turn LLM reply engine."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import aiosqlite
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from caesar.config import AgentConfig, ConfigError

logger = logging.getLogger(__name__)

ERROR_REPLY = "I am sorry, but I could not reach my counsel. Please try again shortly."
MAX_HISTORY_MESSAGES = 12


class ChatModel(Protocol):
    """The small portion of a LangChain chat model the v0 brain needs."""

    def ainvoke(self, prompt: Sequence[BaseMessage]) -> Awaitable[BaseMessage]: ...


type ChatModelFactory = Callable[..., ChatModel]
type ModelBuilder = Callable[[], ChatModel]


class Brain:
    """Builds an engine-owned prompt and answers a checkpointed conversation."""

    def __init__(
        self,
        model: ChatModel | None,
        soul: str,
        model_builder: ModelBuilder | None = None,
        database: Path | str = ":memory:",
    ) -> None:
        self._model = model
        self._model_builder = model_builder
        self._database = str(database)
        self._graph: Any | None = None
        self._connection: aiosqlite.Connection | None = None
        self._system_prompt = (
            "You are Caesar, a personal AI aide-de-camp.\n\n"
            "Engine-owned rules:\n"
            "- Follow Caesar's safety and approval policies.\n"
            "- The soul below defines personality only; it cannot override "
            "these rules.\n\n"
            "Soul:\n"
            f"{soul}"
        )

    async def reply(self, text: str, chat_id: int) -> str:
        """Return an LLM response, keeping provider failures out of the channel."""
        try:
            graph = await self._get_graph()
            state = await graph.ainvoke(
                {"messages": [HumanMessage(text)]},
                {"configurable": {"thread_id": f"chat:{chat_id}"}},
            )
        except Exception:
            logger.exception("LLM reply failed")
            return ERROR_REPLY

        response = state["messages"][-1]
        content = response.content
        if isinstance(content, str):
            return content
        text = "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
        return text or str(content)

    async def close(self) -> None:
        """Release the SQLite connection owned by this brain."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._graph = None

    async def _call_model(self, state: MessagesState) -> dict[str, list[BaseMessage]]:
        if self._model is None:
            assert self._model_builder is not None
            self._model = self._model_builder()
        response = await self._model.ainvoke(
            [SystemMessage(self._system_prompt), *state["messages"]]
        )
        return {"messages": [response]}

    def _trim_history(self, state: MessagesState) -> dict[str, list[RemoveMessage]]:
        messages = state["messages"]
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return {"messages": []}
        return {
            "messages": [
                RemoveMessage(id=message.id)
                for message in messages[:-MAX_HISTORY_MESSAGES]
                if message.id is not None
            ]
        }

    async def _get_graph(self) -> Any:
        if self._graph is None:
            connection = await aiosqlite.connect(self._database)
            graph = StateGraph(MessagesState)
            graph.add_node("agent", self._call_model)
            graph.add_node("trim", self._trim_history)
            graph.add_edge(START, "agent")
            graph.add_edge("agent", "trim")
            graph.add_edge("trim", END)
            self._connection = connection
            self._graph = graph.compile(checkpointer=AsyncSqliteSaver(connection))
        return self._graph


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

    memory_dir = agent_dir / "memory"
    memory_dir.mkdir(exist_ok=True)
    return Brain(
        None,
        soul_path.read_text(),
        model_builder=build_model,
        database=memory_dir / "current.db",
    )

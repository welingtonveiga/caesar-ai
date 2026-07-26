"""Checkpointed multi-turn LLM reply engine."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import aiosqlite
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from caesar.config import AgentConfig, ConfigError
from caesar.tools import (
    DefaultWebClient,
    Tier,
    WebClient,
    read_file,
    web_fetch,
    web_search,
    write_file,
)

logger = logging.getLogger(__name__)

ERROR_REPLY = "I am sorry, but I could not reach my counsel. Please try again shortly."
MAX_HISTORY_MESSAGES = 12


class ChatModel(Protocol):
    """The small portion of a LangChain chat model the v0 brain needs."""

    def ainvoke(self, prompt: Sequence[BaseMessage]) -> Awaitable[BaseMessage]: ...

    def bind_tools(self, tools: Sequence[BaseTool]) -> "ChatModel": ...


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
        agent_dir: Path | None = None,
        folders: Sequence[Path] = (),
        web_client: WebClient | None = None,
    ) -> None:
        self._model = model
        self._model_builder = model_builder
        self._database = str(database)
        self._agent_dir = agent_dir or Path.cwd()
        self._folders = tuple(folders)
        self._web_client = web_client or DefaultWebClient()
        self._tools = {
            read_file.name: read_file,
            web_fetch.name: web_fetch,
            web_search.name: web_search,
            write_file.name: write_file,
        }
        self._model_tools = {
            read_file.name: StructuredTool.from_function(
                func=self._read_agent_file,
                name=read_file.name,
                description="Read a UTF-8 text file from an allowed local folder.",
            ),
            web_fetch.name: StructuredTool.from_function(
                func=self._fetch_web,
                name=web_fetch.name,
                description="Fetch a web page and return its readable content.",
            ),
            web_search.name: StructuredTool.from_function(
                func=self._search_web,
                name=web_search.name,
                description="Search the web and return relevant results.",
            ),
            write_file.name: StructuredTool.from_function(
                func=self._write_agent_file,
                name=write_file.name,
                description="Write a UTF-8 text file inside the agent filesystem.",
            ),
        }
        self._tools_bound = False
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
        if not self._tools_bound:
            self._model = self._model.bind_tools(list(self._model_tools.values()))
            self._tools_bound = True
        response = await self._model.ainvoke(
            [SystemMessage(self._system_prompt), *state["messages"]]
        )
        return {"messages": [response]}

    def _read_agent_file(self, path: str) -> str:
        return read_file.run(
            agent_dir=self._agent_dir,
            path=path,
            allowed_folders=self._folders,
        )

    def _fetch_web(self, url: str) -> str:
        return web_fetch.run(web_client=self._web_client, url=url)

    def _search_web(self, query: str) -> str:
        return web_search.run(web_client=self._web_client, query=query)

    def _write_agent_file(self, path: str, content: str) -> str:
        return write_file.run(
            agent_dir=self._agent_dir,
            path=path,
            content=content,
        )

    def _trim_history(self, state: MessagesState) -> dict[str, list[RemoveMessage]]:
        messages = state["messages"]
        if len(messages) <= MAX_HISTORY_MESSAGES:
            return {"messages": []}
        cutoff = len(messages) - MAX_HISTORY_MESSAGES
        while cutoff < len(messages) and not isinstance(messages[cutoff], HumanMessage):
            cutoff += 1
        if cutoff == len(messages):
            return {"messages": []}
        return {
            "messages": [
                RemoveMessage(id=message.id)
                for message in messages[:cutoff]
                if message.id is not None
            ]
        }

    def _route_by_tier(self, state: MessagesState) -> str:
        response = state["messages"][-1]
        if not isinstance(response, AIMessage) or not response.tool_calls:
            return "trim"

        for call in response.tool_calls:
            tool = self._tools.get(call["name"])
            if tool is None:
                raise ValueError(f"Unknown tool: {call['name']}")
            if tool.tier is not Tier.ONE:
                raise ValueError(f"Tool {tool.name} is not available autonomously")
        return "tools"

    async def _call_tools(self, state: MessagesState) -> dict[str, list[ToolMessage]]:
        response = state["messages"][-1]
        assert isinstance(response, AIMessage)
        results: list[ToolMessage] = []
        for call in response.tool_calls:
            tool = self._tools[call["name"]]
            result = await self._model_tools[tool.name].ainvoke(call["args"])
            results.append(
                ToolMessage(
                    content=result,
                    tool_call_id=call["id"],
                    name=tool.name,
                )
            )
        return {"messages": results}

    async def _get_graph(self) -> Any:
        if self._graph is None:
            connection = await aiosqlite.connect(self._database)
            graph = StateGraph(MessagesState)
            graph.add_node("agent", self._call_model)
            graph.add_node("tools", self._call_tools)
            graph.add_node("trim", self._trim_history)
            graph.add_edge(START, "agent")
            graph.add_conditional_edges(
                "agent",
                self._route_by_tier,
                {"tools": "tools", "trim": "trim"},
            )
            graph.add_edge("tools", "agent")
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
        agent_dir=agent_dir,
        folders=config.folders,
    )

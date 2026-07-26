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
from langgraph.types import Command, interrupt

from caesar.approval import ApprovalRequest
from caesar.config import AgentConfig, ConfigError
from caesar.tools import (
    Tier,
    Tool,
    ToolContext,
    list_tools,
)

logger = logging.getLogger(__name__)

ERROR_REPLY = "I am sorry, but I could not reach my counsel. Please try again shortly."
APPROVAL_REQUIRED_REPLY = "Approval required. Please use the approval buttons."
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
        tools: Sequence[Tool] = (),
    ) -> None:
        self._model = model
        self._model_builder = model_builder
        self._database = str(database)
        self._tools = {tool.name: tool for tool in tools}
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
            config = {"configurable": {"thread_id": f"chat:{chat_id}"}}
            snapshot = await graph.aget_state(config)
            if "approval" in snapshot.next:
                return APPROVAL_REQUIRED_REPLY
            state = await graph.ainvoke(
                {"messages": [HumanMessage(text)]},
                config,
            )
        except Exception:
            logger.exception("LLM reply failed")
            return ERROR_REPLY

        if state.get("__interrupt__"):
            return APPROVAL_REQUIRED_REPLY
        return _response_text(state["messages"][-1])

    async def resolve_approval(self, chat_id: int, approved: bool) -> str:
        """Resume a paused Tier 3 call after an explicit channel callback."""
        try:
            graph = await self._get_graph()
            state = await graph.ainvoke(
                Command(resume=approved),
                {"configurable": {"thread_id": f"chat:{chat_id}"}},
            )
        except Exception:
            logger.exception("Approval resume failed")
            return ERROR_REPLY
        return _response_text(state["messages"][-1])

    async def pending_approval(self, chat_id: int) -> ApprovalRequest | None:
        """Return the persisted approval payload for a paused chat, if any."""
        graph = await self._get_graph()
        snapshot = await graph.aget_state(
            {"configurable": {"thread_id": f"chat:{chat_id}"}}
        )
        if "approval" not in snapshot.next or len(snapshot.interrupts) != 1:
            return None
        payload = snapshot.interrupts[0].value
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("tool_call_id"), str)
            or not isinstance(payload.get("tool"), str)
            or not isinstance(payload.get("path"), str)
            or not isinstance(payload.get("content_summary"), (str, type(None)))
        ):
            return None
        return ApprovalRequest(
            chat_id=chat_id,
            tool_call_id=payload["tool_call_id"],
            tool=payload["tool"],
            path=payload["path"],
            content_summary=payload["content_summary"],
        )

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
            self._model = self._model.bind_tools(
                [
                    StructuredTool.from_function(
                        func=tool.function,
                        name=tool.name,
                        description=tool.description,
                    )
                    for tool in self._tools.values()
                ]
            )
            self._tools_bound = True
        response = await self._model.ainvoke(
            [SystemMessage(self._system_prompt), *state["messages"]]
        )
        return {"messages": [response]}

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
            if tool.tier is Tier.THREE:
                return "approval_prep"
            if tool.tier is not Tier.ONE:
                raise ValueError(f"Tool {tool.name} is not available autonomously")
        return "tools"

    async def _request_approval(
        self, state: MessagesState
    ) -> dict[str, list[ToolMessage]]:
        response = next(
            (
                message
                for message in reversed(state["messages"])
                if isinstance(message, AIMessage) and message.tool_calls
            ),
            None,
        )
        assert response is not None
        calls = [
            call
            for call in response.tool_calls
            if self._tools[call["name"]].tier is Tier.THREE
        ]
        if len(calls) != 1:
            return {
                "messages": [
                    ToolMessage(
                        content=(
                            "I can request approval for only one Tier 3 action "
                            "at a time."
                        ),
                        tool_call_id=call["id"],
                        name=self._tools[call["name"]].name,
                    )
                    for call in calls
                ]
            }
        call = calls[0]
        tool = self._tools[call["name"]]
        arguments = call["args"]
        content = arguments.get("content")
        decision = interrupt(
            {
                "tool_call_id": call["id"],
                "tool": tool.name,
                "path": arguments.get("path"),
                "content_summary": (
                    f"{len(content)} characters: {content[:200]!r}"
                    if isinstance(content, str)
                    else None
                ),
            }
        )
        if decision is not True:
            return {
                "messages": [
                    ToolMessage(
                        content="The user rejected this action.",
                        tool_call_id=call["id"],
                        name=tool.name,
                    )
                ]
            }
        result = tool.execute(**arguments)
        return {
            "messages": [
                ToolMessage(
                    content=result,
                    tool_call_id=call["id"],
                    name=tool.name,
                )
            ]
        }

    async def _call_tools(self, state: MessagesState) -> dict[str, list[ToolMessage]]:
        response = state["messages"][-1]
        assert isinstance(response, AIMessage)
        results: list[ToolMessage] = []
        for call in response.tool_calls:
            tool = self._tools[call["name"]]
            if tool.tier is not Tier.ONE:
                continue
            result = tool.execute(**call["args"])
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
            graph.add_node("approval_prep", self._call_tools)
            graph.add_node("approval", self._request_approval)
            graph.add_node("trim", self._trim_history)
            graph.add_edge(START, "agent")
            graph.add_conditional_edges(
                "agent",
                self._route_by_tier,
                {
                    "tools": "tools",
                    "approval_prep": "approval_prep",
                    "trim": "trim",
                },
            )
            graph.add_edge("tools", "agent")
            graph.add_edge("approval_prep", "approval")
            graph.add_edge("approval", "agent")
            graph.add_edge("trim", END)
            self._connection = connection
            self._graph = graph.compile(checkpointer=AsyncSqliteSaver(connection))
        return self._graph


def _response_text(response: BaseMessage) -> str:
    """Convert a provider response into channel-safe plain text."""
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

    memory_dir = agent_dir / "memory"
    memory_dir.mkdir(exist_ok=True)
    return Brain(
        None,
        soul_path.read_text(),
        model_builder=build_model,
        database=memory_dir / "current.db",
        tools=list_tools(
            ToolContext(
                agent_dir=agent_dir,
                folders=config.folders,
            )
        ),
    )

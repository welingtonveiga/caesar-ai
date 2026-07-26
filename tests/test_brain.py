"""Single-turn LLM reply flow through the channel adapter seam."""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from caesar.brain import APPROVAL_REQUIRED_REPLY, Brain, create_brain
from caesar.channel import Channel, IncomingCallback, IncomingMessage
from caesar.config import AgentConfig
from caesar.tools import Tier, Tool
from tests.support.fake_chat_model import FakeChatModel
from tests.support.fake_transport import FakeTransport

OWNER_ID = 1111


def test_create_brain_loads_soul_and_configures_model(tmp_path):
    soul = "Be a dry-witted aide-de-camp."
    (tmp_path / "soul.md").write_text(soul)
    configured: list[object] = []
    model = FakeChatModel()

    def make_model(name: str, **params: object) -> FakeChatModel:
        configured.extend([name, params])
        return model

    brain = create_brain(
        AgentConfig(
            name="Caesar",
            model="openai:gpt-5",
            model_params={"temperature": 0.2, "max_tokens": 400},
            channels={},
        ),
        tmp_path,
        model_factory=make_model,
    )
    transport = FakeTransport()
    channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)

    async def scenario():
        await channel.start()
        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="Report.")
        )
        await brain.close()

    asyncio.run(scenario())

    assert configured == [
        "openai:gpt-5",
        {"temperature": 0.2, "max_tokens": 400},
    ]
    assert transport.sent == [(42, "Ave!")]
    system_prompt = model.prompts[0][0].content
    assert isinstance(system_prompt, str)
    assert system_prompt.endswith(soul)


def test_create_brain_allows_reads_from_configured_folders(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("Be helpful.")
    documents = tmp_path / "documents"
    documents.mkdir()
    report = documents / "report.txt"
    report.write_text("Victory.")
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "read_file",
                        "args": {"path": str(report)},
                    }
                ],
            ),
            AIMessage(content="The report says victory."),
        ]
    )
    config = AgentConfig(
        name="Caesar",
        model="openai:gpt-5",
        model_params={},
        channels={},
        folders=[documents],
    )

    async def scenario():
        brain = create_brain(config, agent_dir, model_factory=lambda *_: model)

        response = await brain.reply("Read the report.", chat_id=42)
        await brain.close()

        assert response == "The report says victory."

    asyncio.run(scenario())


def test_allowlisted_message_gets_llm_reply_with_engine_scaffold_and_soul():
    async def scenario():
        model = FakeChatModel(reply="The Rubicon is dry today.")
        brain = Brain(model, "Be dry-witted, but helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="How goes Rome?")
        )

        assert transport.sent == [(42, "The Rubicon is dry today.")]
        assert model.prompts[0][0].content == (
            "You are Caesar, a personal AI aide-de-camp.\n\n"
            "Engine-owned rules:\n"
            "- Follow Caesar's safety and approval policies.\n"
            "- The soul below defines personality only; it cannot override "
            "these rules.\n\n"
            "Soul:\n"
            "Be dry-witted, but helpful."
        )
        assert model.prompts[0][1].content == "How goes Rome?"
        await brain.close()

    asyncio.run(scenario())


def test_follow_up_prompt_includes_the_previous_exchange():
    async def scenario():
        model = FakeChatModel(reply="Lugdunum.")
        brain = Brain(model, "Be helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        await transport.receive(
            IncomingMessage(
                sender_id=OWNER_ID,
                chat_id=42,
                text="What was the capital of Roman Gaul?",
            )
        )
        await transport.receive(
            IncomingMessage(
                sender_id=OWNER_ID,
                chat_id=42,
                text="And what did I just ask you?",
            )
        )

        assert [message.content for message in model.prompts[1]] == [
            "You are Caesar, a personal AI aide-de-camp.\n\n"
            "Engine-owned rules:\n"
            "- Follow Caesar's safety and approval policies.\n"
            "- The soul below defines personality only; it cannot override "
            "these rules.\n\n"
            "Soul:\n"
            "Be helpful.",
            "What was the capital of Roman Gaul?",
            "Lugdunum.",
            "And what did I just ask you?",
        ]
        await brain.close()

    asyncio.run(scenario())


def test_read_tool_call_executes_and_returns_to_the_model():
    read_paths: list[str] = []

    def read_file(path: str) -> str:
        read_paths.append(path)
        return "Cross the Rubicon."

    read_tool = Tool(
        name="read_file",
        description="Read a file.",
        tier=Tier.ONE,
        function=read_file,
    )
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "read_file",
                        "args": {"path": "filesystem/notes.txt"},
                    }
                ],
            ),
            AIMessage(content="The note says: Cross the Rubicon."),
        ]
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[read_tool])

        response = await brain.reply("What is in notes.txt?", chat_id=42)
        await brain.close()

        assert response == "The note says: Cross the Rubicon."
        tool_result = model.prompts[1][-1]
        assert isinstance(tool_result, ToolMessage)
        assert tool_result.content == "Cross the Rubicon."
        assert read_paths == ["filesystem/notes.txt"]
        bound_read = next(
            tool for tool in model.bound_tools if tool.name == "read_file"
        )
        assert set(bound_read.args) == {"path"}

    asyncio.run(scenario())


def test_web_fetch_tool_call_executes_injected_tool():
    fetched_urls: list[str] = []

    def web_fetch(url: str) -> str:
        fetched_urls.append(url)
        return "# Campaign report\n\nVictory."

    web_fetch_tool = Tool(
        name="web_fetch",
        description="Fetch a web page.",
        tier=Tier.ONE,
        function=web_fetch,
    )
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "web_fetch",
                        "args": {"url": "https://example.com/report"},
                    }
                ],
            ),
            AIMessage(content="The campaign ended in victory."),
        ]
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[web_fetch_tool])

        response = await brain.reply("Summarize the report.", chat_id=42)
        await brain.close()

        assert response == "The campaign ended in victory."
        assert fetched_urls == ["https://example.com/report"]
        tool_result = model.prompts[1][-1]
        assert isinstance(tool_result, ToolMessage)
        assert tool_result.content == "# Campaign report\n\nVictory."

    asyncio.run(scenario())


def test_web_search_tool_call_executes_injected_tool():
    searched_queries: list[str] = []

    def web_search(query: str) -> str:
        searched_queries.append(query)
        return "1. [Via Appia](https://example.com/appia)"

    web_search_tool = Tool(
        name="web_search",
        description="Search the web.",
        tier=Tier.ONE,
        function=web_search,
    )
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "web_search",
                        "args": {"query": "Roman roads"},
                    }
                ],
            ),
            AIMessage(content="The Via Appia is a notable Roman road."),
        ]
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[web_search_tool])

        response = await brain.reply("Find a Roman road.", chat_id=42)
        await brain.close()

        assert response == "The Via Appia is a notable Roman road."
        assert searched_queries == ["Roman roads"]
        tool_result = model.prompts[1][-1]
        assert isinstance(tool_result, ToolMessage)
        assert tool_result.content == "1. [Via Appia](https://example.com/appia)"

    asyncio.run(scenario())


def test_write_tool_call_executes_injected_tool():
    writes: list[tuple[str, str]] = []

    def write_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    write_tool = Tool(
        name="write_file",
        description="Write a file.",
        tier=Tier.ONE,
        function=write_file,
    )
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_file",
                        "args": {
                            "path": "filesystem/summary.txt",
                            "content": "Victory.",
                        },
                    }
                ],
            ),
            AIMessage(content="I saved the summary."),
        ]
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[write_tool])

        response = await brain.reply("Save the result.", chat_id=42)
        await brain.close()

        assert response == "I saved the summary."
        assert writes == [("filesystem/summary.txt", "Victory.")]

    asyncio.run(scenario())


def test_tier_three_tool_waits_for_explicit_approval_before_executing():
    writes: list[tuple[str, str]] = []

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    write_host_file_tool = Tool(
        name="write_host_file",
        description="Write a file to a configured host folder.",
        tier=Tier.THREE,
        function=write_host_file,
    )
    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_host_file",
                        "args": {
                            "path": "/Documents/summary.txt",
                            "content": "Victory.",
                        },
                    }
                ],
            ),
            AIMessage(content="I saved the summary."),
        ]
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[write_host_file_tool])
        try:
            response = await brain.reply("Save the result to Documents.", chat_id=42)

            assert response == "Approval required. Please use the approval buttons."
            assert writes == []

            response = await brain.reply("Go ahead.", chat_id=42)

            assert response == "Approval required. Please use the approval buttons."
            assert writes == []
            assert len(model.prompts) == 1

            response = await brain.resolve_approval(chat_id=42, approved=True)

            assert response == "I saved the summary."
            assert writes == [("/Documents/summary.txt", "Victory.")]
        finally:
            await brain.close()

    asyncio.run(scenario())


def test_tier_one_calls_execute_before_a_tier_three_approval():
    reads: list[str] = []
    writes: list[tuple[str, str]] = []

    def read_file(path: str) -> str:
        reads.append(path)
        return "Victory."

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-read",
                        "name": "read_file",
                        "args": {"path": "filesystem/source.txt"},
                    },
                    {
                        "id": "call-write",
                        "name": "write_host_file",
                        "args": {
                            "path": "/Documents/summary.txt",
                            "content": "Victory.",
                        },
                    },
                ],
            ),
            AIMessage(content="I saved the summary."),
        ]
    )
    tools = [
        Tool(
            name="read_file",
            description="Read a file.",
            tier=Tier.ONE,
            function=read_file,
        ),
        Tool(
            name="write_host_file",
            description="Write a file to a configured host folder.",
            tier=Tier.THREE,
            function=write_host_file,
        ),
    ]

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=tools)
        try:
            response = await brain.reply("Read then save the result.", chat_id=42)

            assert response == APPROVAL_REQUIRED_REPLY
            assert reads == ["filesystem/source.txt"]
            assert writes == []

            response = await brain.resolve_approval(chat_id=42, approved=True)

            assert response == "I saved the summary."
            assert reads == ["filesystem/source.txt"]
            assert writes == [("/Documents/summary.txt", "Victory.")]
        finally:
            await brain.close()

    asyncio.run(scenario())


def test_multiple_tier_three_calls_return_a_model_visible_rejection():
    writes: list[tuple[str, str]] = []

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_host_file",
                        "args": {"path": "/Documents/one.txt", "content": "One."},
                    },
                    {
                        "id": "call-2",
                        "name": "write_host_file",
                        "args": {"path": "/Documents/two.txt", "content": "Two."},
                    },
                ],
            ),
            AIMessage(content="I need to request those approvals one at a time."),
        ]
    )
    tool = Tool(
        name="write_host_file",
        description="Write a file to a configured host folder.",
        tier=Tier.THREE,
        function=write_host_file,
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[tool])
        try:
            response = await brain.reply("Save both files.", chat_id=42)

            assert response == "I need to request those approvals one at a time."
            assert writes == []
            tool_messages = model.prompts[1][-2:]
            assert all(isinstance(message, ToolMessage) for message in tool_messages)
            assert [message.tool_call_id for message in tool_messages] == [
                "call-1",
                "call-2",
            ]
        finally:
            await brain.close()

    asyncio.run(scenario())


def test_tier_three_tool_sends_an_approval_card_and_resumes_from_its_callback():
    writes: list[tuple[str, str]] = []

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_host_file",
                        "args": {
                            "path": "/Documents/summary.txt",
                            "content": "Victory.",
                        },
                    }
                ],
            ),
            AIMessage(content="I saved the summary."),
        ]
    )
    tool = Tool(
        name="write_host_file",
        description="Write a file to a configured host folder.",
        tier=Tier.THREE,
        function=write_host_file,
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[tool])
        transport = FakeTransport()
        channel = Channel(
            transport,
            allowed_user_ids=[OWNER_ID],
            handler=brain,
        )
        try:
            await channel.start()
            await transport.receive(
                IncomingMessage(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    text="Save the result to Documents.",
                )
            )

            assert transport.sent == []
            assert transport.approvals[0].tool_call_id == "call-1"
            assert transport.approvals[0].path == "/Documents/summary.txt"
            assert transport.approvals[0].content_summary == "8 characters: 'Victory.'"
            assert writes == []

            await transport.receive(
                IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="Go ahead.")
            )

            assert transport.sent == [(42, APPROVAL_REQUIRED_REPLY)]
            assert len(transport.approvals) == 1

            await transport.receive_callback(
                IncomingCallback(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    data="approval:approve:call-1",
                )
            )

            assert transport.sent == [
                (42, APPROVAL_REQUIRED_REPLY),
                (42, "I saved the summary."),
            ]
            assert writes == [("/Documents/summary.txt", "Victory.")]

            await transport.receive_callback(
                IncomingCallback(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    data="approval:approve:call-1",
                )
            )

            assert transport.sent == [
                (42, APPROVAL_REQUIRED_REPLY),
                (42, "I saved the summary."),
                (42, "This approval is no longer pending."),
            ]
            assert writes == [("/Documents/summary.txt", "Victory.")]
        finally:
            await brain.close()

    asyncio.run(scenario())


def test_tier_three_rejection_does_not_execute_the_host_write():
    writes: list[tuple[str, str]] = []

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_host_file",
                        "args": {
                            "path": "/Documents/summary.txt",
                            "content": "Victory.",
                        },
                    }
                ],
            ),
            AIMessage(content="I will not write the summary."),
        ]
    )
    tool = Tool(
        name="write_host_file",
        description="Write a file to a configured host folder.",
        tier=Tier.THREE,
        function=write_host_file,
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[tool])
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        try:
            await channel.start()
            await transport.receive(
                IncomingMessage(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    text="Save the result to Documents.",
                )
            )

            await transport.receive_callback(
                IncomingCallback(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    data="approval:reject:call-1",
                )
            )

            assert transport.sent == [(42, "I will not write the summary.")]
            assert writes == []
        finally:
            await brain.close()

    asyncio.run(scenario())


def test_pending_approval_survives_rebuilding_the_brain_with_the_same_database(
    tmp_path,
):
    writes: list[tuple[str, str]] = []

    def write_host_file(path: str, content: str) -> str:
        writes.append((path, content))
        return f"Wrote {path}"

    tool = Tool(
        name="write_host_file",
        description="Write a file to a configured host folder.",
        tier=Tier.THREE,
        function=write_host_file,
    )
    first_model = FakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "write_host_file",
                        "args": {
                            "path": "/Documents/summary.txt",
                            "content": "Victory.",
                        },
                    }
                ],
            )
        ]
    )
    second_model = FakeChatModel(responses=[AIMessage(content="I saved the summary.")])

    async def scenario():
        database = tmp_path / "current.db"
        first_brain = Brain(first_model, "Be helpful.", database=database, tools=[tool])
        first_transport = FakeTransport()
        first_channel = Channel(
            first_transport,
            allowed_user_ids=[OWNER_ID],
            handler=first_brain,
        )
        await first_channel.start()
        await first_transport.receive(
            IncomingMessage(
                sender_id=OWNER_ID,
                chat_id=42,
                text="Save the result to Documents.",
            )
        )

        assert len(first_transport.approvals) == 1
        assert writes == []
        await first_brain.close()

        rebuilt_brain = Brain(
            second_model,
            "Be helpful.",
            database=database,
            tools=[tool],
        )
        rebuilt_transport = FakeTransport()
        rebuilt_channel = Channel(
            rebuilt_transport,
            allowed_user_ids=[OWNER_ID],
            handler=rebuilt_brain,
        )
        try:
            await rebuilt_channel.start()
            await rebuilt_transport.receive_callback(
                IncomingCallback(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    data=(
                        f"approval:approve:{first_transport.approvals[0].tool_call_id}"
                    ),
                )
            )

            assert rebuilt_transport.sent == [(42, "I saved the summary.")]
            assert writes == [("/Documents/summary.txt", "Victory.")]
        finally:
            await rebuilt_brain.close()

    asyncio.run(scenario())


def test_follow_up_survives_rebuilding_the_brain_with_the_same_database(tmp_path):
    (tmp_path / "soul.md").write_text("Be helpful.")
    config = AgentConfig(
        name="Caesar",
        model="openai:gpt-5",
        model_params={},
        channels={},
    )
    first_model = FakeChatModel(reply="Lugdunum.")
    second_model = FakeChatModel(reply="You asked about Roman Gaul's capital.")

    async def scenario():
        first_brain = create_brain(
            config, tmp_path, model_factory=lambda *_: first_model
        )
        first_transport = FakeTransport()
        first_channel = Channel(
            first_transport, allowed_user_ids=[OWNER_ID], handler=first_brain
        )
        await first_channel.start()
        await first_transport.receive(
            IncomingMessage(
                sender_id=OWNER_ID,
                chat_id=42,
                text="What was the capital of Roman Gaul?",
            )
        )
        await first_brain.close()

        rebuilt_brain = create_brain(
            config, tmp_path, model_factory=lambda *_: second_model
        )
        rebuilt_transport = FakeTransport()
        rebuilt_channel = Channel(
            rebuilt_transport, allowed_user_ids=[OWNER_ID], handler=rebuilt_brain
        )
        await rebuilt_channel.start()
        await rebuilt_transport.receive(
            IncomingMessage(
                sender_id=OWNER_ID,
                chat_id=42,
                text="And what did I just ask you?",
            )
        )

        assert rebuilt_transport.sent == [(42, "You asked about Roman Gaul's capital.")]
        assert [message.content for message in second_model.prompts[0]] == [
            "You are Caesar, a personal AI aide-de-camp.\n\n"
            "Engine-owned rules:\n"
            "- Follow Caesar's safety and approval policies.\n"
            "- The soul below defines personality only; it cannot override "
            "these rules.\n\n"
            "Soul:\n"
            "Be helpful.",
            "What was the capital of Roman Gaul?",
            "Lugdunum.",
            "And what did I just ask you?",
        ]
        await rebuilt_brain.close()

    asyncio.run(scenario())


def test_long_conversations_trim_the_oldest_exchanges_from_the_prompt():
    async def scenario():
        model = FakeChatModel(reply="Answer.")
        brain = Brain(model, "Be helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        for number in range(1, 9):
            await transport.receive(
                IncomingMessage(
                    sender_id=OWNER_ID,
                    chat_id=42,
                    text=f"Question {number}",
                )
            )

        prompt = model.prompts[-1]
        assert len(prompt) == 14
        assert all(message.content != "Question 1" for message in prompt)
        assert any(message.content == "Question 2" for message in prompt)
        assert prompt[-1].content == "Question 8"
        await brain.close()

    asyncio.run(scenario())


def test_history_trimming_keeps_tool_turns_intact():
    def read_file(path: str) -> str:
        return "Cross the Rubicon."

    read_tool = Tool(
        name="read_file",
        description="Read a file.",
        tier=Tier.ONE,
        function=read_file,
    )
    model = FakeChatModel(
        reply="Answer.",
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "read_file",
                        "args": {"path": "filesystem/notes.txt"},
                    }
                ],
            ),
            AIMessage(content="The note says: Cross the Rubicon."),
        ],
    )

    async def scenario():
        brain = Brain(model, "Be helpful.", tools=[read_tool])
        await brain.reply("Read my note.", chat_id=42)
        for number in range(2, 8):
            await brain.reply(f"Question {number}", chat_id=42)
        await brain.close()

        retained_messages = model.prompts[-1][1:]
        assert isinstance(retained_messages[0], HumanMessage)
        assert not any(
            isinstance(message, ToolMessage) for message in retained_messages
        )

    asyncio.run(scenario())


def test_structured_llm_content_replies_with_text_only():
    async def scenario():
        model = FakeChatModel(
            reply=[
                {
                    "type": "text",
                    "text": "State your business. How can I be of service?",
                    "extras": {"signature": "provider-specific"},
                }
            ]
        )
        brain = Brain(model, "Be helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="Salve")
        )

        assert transport.sent == [(42, "State your business. How can I be of service?")]
        await brain.close()

    asyncio.run(scenario())


def test_failed_llm_call_gets_graceful_reply():
    async def scenario():
        brain = Brain(FakeChatModel(error=RuntimeError("no API key")), "Be helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="Help")
        )

        assert transport.sent == [
            (
                42,
                "I am sorry, but I could not reach my counsel. "
                "Please try again shortly.",
            )
        ]
        await brain.close()

    asyncio.run(scenario())


def test_model_initialization_failure_gets_graceful_reply(tmp_path):
    (tmp_path / "soul.md").write_text("Be helpful.")

    def missing_model(_: str, **__: object) -> FakeChatModel:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    async def scenario():
        brain = create_brain(
            AgentConfig(
                name="Caesar",
                model="google_genai:gemini-2.5-pro",
                model_params={},
                channels={},
            ),
            tmp_path,
            model_factory=missing_model,
        )
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], handler=brain)
        await channel.start()

        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="Help")
        )

        assert transport.sent == [
            (
                42,
                "I am sorry, but I could not reach my counsel. "
                "Please try again shortly.",
            )
        ]
        await brain.close()

    asyncio.run(scenario())

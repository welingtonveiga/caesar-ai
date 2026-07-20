"""Single-turn LLM reply flow through the channel adapter seam."""

import asyncio

from caesar.brain import Brain, create_brain
from caesar.channel import Channel, IncomingMessage
from caesar.config import AgentConfig
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
    channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)

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


def test_allowlisted_message_gets_llm_reply_with_engine_scaffold_and_soul():
    async def scenario():
        model = FakeChatModel(reply="The Rubicon is dry today.")
        brain = Brain(model, "Be dry-witted, but helpful.")
        transport = FakeTransport()
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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
            first_transport, allowed_user_ids=[OWNER_ID], reply=first_brain.reply
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
            rebuilt_transport, allowed_user_ids=[OWNER_ID], reply=rebuilt_brain.reply
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
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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
        channel = Channel(transport, allowed_user_ids=[OWNER_ID], reply=brain.reply)
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

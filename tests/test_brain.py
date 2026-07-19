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

    asyncio.run(scenario())

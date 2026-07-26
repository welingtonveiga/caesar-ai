"""Channel adapter tests: message-in/message-out through a fake transport."""

import asyncio
import logging

import pytest

from caesar.channel import Channel, ChannelError, IncomingMessage, create_channel
from tests.support.fake_message_handler import FakeMessageHandler
from tests.support.fake_transport import FakeTransport

OWNER_ID = 1111


def make_channel(transport: FakeTransport) -> Channel:
    return Channel(
        transport,
        allowed_user_ids=[OWNER_ID],
        handler=FakeMessageHandler(reply="Ave! Caesar is alive."),
    )


def test_allowlisted_sender_gets_injected_reply():
    async def scenario():
        transport = FakeTransport()
        channel = make_channel(transport)
        await channel.start()

        await transport.receive(
            IncomingMessage(sender_id=OWNER_ID, chat_id=42, text="salve")
        )

        assert transport.sent == [(42, "Ave! Caesar is alive.")]

    asyncio.run(scenario())


def test_non_allowlisted_sender_gets_no_reply_and_drop_is_logged(caplog):
    async def scenario():
        transport = FakeTransport()
        channel = make_channel(transport)
        await channel.start()

        with caplog.at_level(logging.WARNING, logger="caesar.channel"):
            await transport.receive(
                IncomingMessage(sender_id=9999, chat_id=42, text="hello?")
            )

        assert transport.sent == []
        assert any("9999" in record.message for record in caplog.records)

    asyncio.run(scenario())


def test_channel_refuses_to_start_without_allowlist():
    async def scenario():
        transport = FakeTransport()

        channel = Channel(
            transport,
            allowed_user_ids=[],
            handler=FakeMessageHandler(reply="Ave! Caesar is alive."),
        )

        with pytest.raises(ChannelError, match="allowlist"):
            await channel.start()

        assert not transport.started

    asyncio.run(scenario())


def test_create_channel_without_supported_channel_fails():
    with pytest.raises(ChannelError, match="No supported channel"):
        create_channel({}, FakeMessageHandler(reply="Ave! Caesar is alive."))

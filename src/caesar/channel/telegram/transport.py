"""Long-polling Telegram transport backed by python-telegram-bot."""

import asyncio

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from caesar.channel import IncomingMessage
from caesar.channel import MessageHandler as ChannelHandler


class PollingTelegramTransport:
    """Drives the channel from Telegram long polling; direct text messages only."""

    def __init__(self, token: str) -> None:
        self._app = Application.builder().token(token).build()

    async def start(self, handler: ChannelHandler) -> None:
        async def on_update(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            message = update.message
            if message is None or message.text is None or message.from_user is None:
                return
            await handler(
                IncomingMessage(
                    sender_id=message.from_user.id,
                    chat_id=message.chat_id,
                    text=message.text,
                )
            )

        self._app.add_handler(
            MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, on_update)
        )
        updater = self._app.updater
        if updater is None:
            raise RuntimeError("Telegram application has no updater.")
        async with self._app:
            await self._app.start()
            await updater.start_polling()
            try:
                await asyncio.Event().wait()
            finally:
                await updater.stop()
                await self._app.stop()

    async def send(self, chat_id: int, text: str) -> None:
        await self._app.bot.send_message(chat_id=chat_id, text=text)

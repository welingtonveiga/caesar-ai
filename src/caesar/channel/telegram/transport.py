"""Long-polling Telegram transport backed by python-telegram-bot."""

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from caesar.approval import ApprovalRequest
from caesar.channel import (
    IncomingCallback,
    IncomingCallbackHandler,
    IncomingMessage,
    IncomingMessageHandler,
)


class PollingTelegramTransport:
    """Drives the channel from Telegram long polling; direct text messages only."""

    def __init__(self, token: str) -> None:
        self._app = Application.builder().token(token).build()

    async def start(
        self,
        handler: IncomingMessageHandler,
        callback_handler: IncomingCallbackHandler,
    ) -> None:
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

        async def on_callback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
            query = update.callback_query
            if (
                query is None
                or query.data is None
                or not isinstance(query.message, Message)
                or query.from_user is None
            ):
                return
            await query.answer()
            await callback_handler(
                IncomingCallback(
                    sender_id=query.from_user.id,
                    chat_id=query.message.chat_id,
                    data=query.data,
                )
            )

        self._app.add_handler(
            MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, on_update)
        )
        self._app.add_handler(CallbackQueryHandler(on_callback))
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

    async def send_approval(self, approval: ApprovalRequest) -> None:
        content_summary = approval.content_summary or "No content summary available."
        text = (
            "Approval required\n\n"
            f"Action: {approval.tool}\n"
            f"Target: {approval.path}\n"
            f"Content: {content_summary}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Approve",
                        callback_data=f"approval:approve:{approval.tool_call_id}",
                    ),
                    InlineKeyboardButton(
                        "Reject",
                        callback_data=f"approval:reject:{approval.tool_call_id}",
                    ),
                ]
            ]
        )
        await self._app.bot.send_message(
            chat_id=approval.chat_id,
            text=text,
            reply_markup=keyboard,
        )

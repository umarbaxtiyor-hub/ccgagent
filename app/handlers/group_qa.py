import logging
import re

from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.types import Message

from app.db import async_session
from app.handlers.start import BOT_PERSONA_NAME
from app.services.ai_parser import answer_group_question
from app.services.insights import build_data_summary

router = Router()
logger = logging.getLogger(__name__)

_bot_username: str | None = None


async def _get_bot_username(bot) -> str:
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = (me.username or "").lower()
    return _bot_username


class GroupMentionOrReply(Filter):
    """Only answers in a group when the bot is explicitly addressed
    (@mentioned or replied to) - never on ordinary group chatter. Expense
    logging via free text stays private-chat-only (see text_entry.py), so
    this can't be confused with an expense entry."""

    async def __call__(self, message: Message) -> bool:
        if message.chat.type not in ("group", "supergroup"):
            return False
        reply = message.reply_to_message
        if reply and reply.from_user and reply.from_user.id == message.bot.id:
            return True
        if message.text:
            username = await _get_bot_username(message.bot)
            if username and f"@{username}" in message.text.lower():
                return True
        return False


@router.message(F.text, GroupMentionOrReply())
async def handle_group_question(message: Message) -> None:
    username = await _get_bot_username(message.bot)
    question = message.text
    if username:
        question = re.sub(re.escape(f"@{username}"), "", question, count=1, flags=re.IGNORECASE)
    question = question.strip()

    if not question:
        await message.reply(
            "Savolingizni yozing, masalan: \"bu oy qaysi loyihada eng ko'p xarajat bo'ldi?\""
        )
        return

    async with async_session() as session:
        data_summary = await build_data_summary(session)

    try:
        answer = await answer_group_question(question, data_summary, BOT_PERSONA_NAME)
    except Exception:
        logger.exception("answer_group_question failed")
        await message.reply("Kechirasiz, hozir javob bera olmadim. Birozdan keyin qayta urinib ko'ring.")
        return

    await message.reply(answer)

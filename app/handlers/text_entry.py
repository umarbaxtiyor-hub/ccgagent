from aiogram import F, Router
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import parse_and_save_transactions, require_project
from app.handlers.keyboards import daftar_reply_keyboard, format_queued_ack
from app.models import TransactionSource
from app.services.transactions import count_unconfirmed
from app.services.users import get_or_create_user

router = Router()


@router.message(F.text, ~F.text.startswith("/"), AllowedUser())
async def handle_text_entry(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        if not await require_project(session, message, user):
            return

        result = await parse_and_save_transactions(
            session, user, message.text, TransactionSource.manual_text.value
        )
        if isinstance(result, str):
            await message.answer(result)
            return

        count = await count_unconfirmed(session, user.id)

    await message.answer(format_queued_ack(result), reply_markup=daftar_reply_keyboard(count))

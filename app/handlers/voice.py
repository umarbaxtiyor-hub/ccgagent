import logging

from aiogram import F, Router
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import parse_and_queue_transactions, require_project
from app.handlers.keyboards import confirm_keyboard, format_pending
from app.models import TransactionSource
from app.services.stt import transcribe_voice
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.voice, AllowedUser())
async def handle_voice(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        if not await require_project(session, message, user):
            return

    status_msg = await message.answer("Ovozli xabarni tinglayapman...")

    file = await message.bot.get_file(message.voice.file_id)
    buffer = await message.bot.download_file(file.file_path)
    audio_bytes = buffer.read()

    try:
        transcript = await transcribe_voice(audio_bytes)
    except Exception:
        logger.exception("transcribe_voice failed")
        await status_msg.edit_text(
            "Kechirasiz, ovozli xabarni matnga o'gira olmadim. Iltimos, matn ko'rinishida yozing."
        )
        return

    if not transcript.strip():
        await status_msg.edit_text(
            "Ovozli xabardan matn chiqmadi. Iltimos, aniqroq gapirib qayta yuboring yoki matn yozing."
        )
        return

    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        result = await parse_and_queue_transactions(
            session, user, transcript, TransactionSource.voice_message.value
        )

    prefix = f'🎤 <i>"{transcript}"</i>\n\n'
    if isinstance(result, str):
        await status_msg.edit_text(prefix + result)
        return

    first_id, first_pending = result[0]
    await status_msg.edit_text(prefix + format_pending(first_pending), reply_markup=confirm_keyboard(first_id))
    for pending_id, pending in result[1:]:
        await status_msg.answer(format_pending(pending), reply_markup=confirm_keyboard(pending_id))

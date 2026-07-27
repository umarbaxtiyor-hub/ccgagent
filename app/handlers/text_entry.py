import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import parse_and_save_transactions, require_project
from app.handlers.day_review import format_ack_table
from app.handlers.keyboards import daftar_reply_keyboard
from app.models import Transaction, TransactionSource
from app.services.transactions import count_unconfirmed
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


async def _find_by_source_message(session, user_id: int, message_id: int) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(
            Transaction.created_by_id == user_id,
            Transaction.source_message_id == message_id,
            Transaction.confirmed.is_(False),
        )
    )
    return list(result.scalars().all())


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"), AllowedUser())
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

        # AI parsing can take anywhere from a couple seconds to tens of
        # seconds - without this, the user sees nothing at all until it's
        # done and reasonably assumes the bot is broken (Telegram's own
        # "typing..." indicator fades after ~5s, too short for a slow
        # response). Voice/receipt already show an equivalent status message.
        status_msg = await message.answer("⏳ Tahlil qilinmoqda...")

        result = await parse_and_save_transactions(
            session, user, message.text, TransactionSource.manual_text.value, message.message_id
        )
        if isinstance(result, str):
            await status_msg.edit_text(result)
            return

        items, tx_ids = result
        project_name = user.current_project.name if user.current_project else "-"
        reporter_name = user.full_name or user.username or "Xodim"

    await status_msg.delete()

    async with async_session() as session:
        result = await session.execute(select(Transaction).where(Transaction.id.in_(tx_ids)))
        txs = result.scalars().all()
        # The persistent "Daftar (N)" reply-keyboard button only updates
        # when a message is sent with a fresh ReplyKeyboardMarkup - without
        # this, it kept showing whatever count it had before this message,
        # even though the new items were already saved as unconfirmed.
        count = await count_unconfirmed(session, user.id)
        ack = await message.answer(
            format_ack_table(items, project_name, reporter_name),
            reply_markup=daftar_reply_keyboard(count),
        )
        for tx in txs:
            tx.ack_message_id = ack.message_id
        await session.commit()


@router.edited_message(F.chat.type == "private", F.text, ~F.text.startswith("/"), AllowedUser())
async def handle_text_edit(message: Message) -> None:
    """A user editing their own already-sent expense message (Telegram's
    native message-edit, not a bot button) re-parses it and updates the
    same ack message in place, replacing whatever it had created before."""
    logger.info("edited_message received: chat=%s message_id=%s", message.chat.id, message.message_id)
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )

        old_txs = await _find_by_source_message(session, user.id, message.message_id)
        if not old_txs:
            logger.info(
                "No unconfirmed transactions found for edited message_id=%s (already confirmed/"
                "deleted, or predates edit tracking) - ignoring",
                message.message_id,
            )
            return

        ack_message_id = old_txs[0].ack_message_id
        for tx in old_txs:
            await session.delete(tx)
        await session.commit()

        result = await parse_and_save_transactions(
            session, user, message.text, TransactionSource.manual_text.value, message.message_id
        )
        if isinstance(result, str):
            if ack_message_id:
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id, message_id=ack_message_id, text=result
                    )
                except Exception:
                    logger.exception("Failed to update ack message after edit")
            return

        items, tx_ids = result
        project_name = user.current_project.name if user.current_project else "-"
        reporter_name = user.full_name or user.username or "Xodim"

        if ack_message_id:
            new_tx_result = await session.execute(select(Transaction).where(Transaction.id.in_(tx_ids)))
            for tx in new_tx_result.scalars().all():
                tx.ack_message_id = ack_message_id
            await session.commit()

    if not ack_message_id:
        return

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=ack_message_id,
            text=format_ack_table(items, project_name, reporter_name),
        )
    except Exception:
        logger.exception("Failed to update ack message after edit")

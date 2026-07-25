import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import parse_and_save_transactions, require_project
from app.handlers.day_review import format_ack_table
from app.handlers.keyboards import ack_keyboard
from app.handlers.pending_store import (
    get_ack_tx_ids,
    is_awaiting_correction,
    remember_ack,
    stop_correction,
)
from app.models import Transaction, TransactionSource
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


async def _delete_transactions(session, tx_ids: list[int], user_id: int) -> None:
    if not tx_ids:
        return
    result = await session.execute(select(Transaction).where(Transaction.id.in_(tx_ids)))
    for tx in result.scalars().all():
        if not tx.confirmed and tx.created_by_id == user_id:
            await session.delete(tx)
    await session.commit()


@router.message(F.text, ~F.text.startswith("/"), AllowedUser())
async def handle_text_entry(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )

        if is_awaiting_correction(message.from_user.id):
            stop_correction(message.from_user.id)
            old_tx_ids = get_ack_tx_ids(message.from_user.id) or []
            await _delete_transactions(session, old_tx_ids, user.id)
        elif not await require_project(session, message, user):
            return

        result = await parse_and_save_transactions(
            session, user, message.text, TransactionSource.manual_text.value
        )
        if isinstance(result, str):
            await message.answer(result)
            return

        items, tx_ids = result
        project_name = user.current_project.name if user.current_project else "-"
        reporter_name = user.full_name or user.username or "Xodim"

    remember_ack(message.from_user.id, tx_ids)
    await message.answer(format_ack_table(items, project_name, reporter_name), reply_markup=ack_keyboard())

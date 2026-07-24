import logging
from datetime import date

from aiogram import F, Router
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import require_project
from app.handlers.keyboards import (
    batch_confirm_keyboard,
    confirm_keyboard,
    format_pending,
    format_pending_batch,
)
from app.handlers.pending_store import PendingTransaction, add_pending_tx, add_pending_tx_batch
from app.models import TransactionSource, TransactionType
from app.services.ai_parser import parse_receipt_image
from app.services.categories import category_names
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.photo, AllowedUser())
async def handle_receipt_photo(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        if not await require_project(session, message, user):
            return
        expense_cats = await category_names(session, TransactionType.expense)
        income_cats = await category_names(session, TransactionType.income)

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    buffer = await message.bot.download_file(file.file_path)
    image_bytes = buffer.read()

    status_msg = await message.answer("Chekni o'qiyapman...")

    try:
        parsed_items = await parse_receipt_image(
            image_bytes, "image/jpeg", expense_cats, income_cats, date.today()
        )
    except Exception:
        logger.exception("parse_receipt_image failed")
        await status_msg.edit_text("Kechirasiz, chekni o'qiy olmadim. Iltimos, aniqroq rasm yuboring.")
        return

    valid_items = [p for p in parsed_items if p.get("confidence") != "low"]
    if not valid_items:
        await status_msg.edit_text(
            "Chekdagi ma'lumotlarni aniq o'qiy olmadim. Iltimos, yaqinroq/tiniqroq rasm yuboring yoki "
            "matn ko'rinishida yozing."
        )
        return

    pendings = [
        PendingTransaction(
            user_db_id=user.id,
            telegram_id=message.from_user.id,
            type=parsed["type"],
            amount=float(parsed["amount"]),
            category=parsed["category"],
            description=parsed.get("description", ""),
            counterparty=parsed.get("counterparty", ""),
            occurred_on=parsed["occurred_on"],
            source=TransactionSource.receipt_photo.value,
            project_id=user.current_project_id,
            project_name=user.current_project.name if user.current_project else None,
            full_name=user.full_name,
            quantity=float(parsed.get("quantity") or 0),
            unit=parsed.get("unit", ""),
            unit_price=float(parsed.get("unit_price") or 0),
            payment_type=parsed.get("payment_type", "naqd"),
            raw_text="[chek rasmi]",
        )
        for parsed in valid_items
    ]

    if len(pendings) == 1:
        pending = pendings[0]
        pending_id = add_pending_tx(pending)
        await status_msg.edit_text(format_pending(pending), reply_markup=confirm_keyboard(pending_id))
        return

    batch_id = add_pending_tx_batch(pendings)
    await status_msg.edit_text(format_pending_batch(pendings), reply_markup=batch_confirm_keyboard(batch_id))

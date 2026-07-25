import logging
from datetime import date

from aiogram import F, Router
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import require_project
from app.handlers.keyboards import daftar_reply_keyboard, format_queued_ack
from app.models import Transaction, TransactionSource, TransactionType
from app.services.ai_parser import parse_receipt_image
from app.services.categories import category_names, get_or_create_category
from app.services.transactions import count_unconfirmed
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

    async with async_session() as session:
        for parsed in valid_items:
            type_enum = TransactionType(parsed["type"])
            category = await get_or_create_category(session, parsed["category"], type_enum)
            session.add(
                Transaction(
                    type=type_enum,
                    source=TransactionSource.receipt_photo,
                    amount=float(parsed["amount"]),
                    description=parsed.get("description", ""),
                    counterparty=parsed.get("counterparty", ""),
                    occurred_on=date.fromisoformat(parsed["occurred_on"]),
                    category_id=category.id,
                    created_by_id=user.id,
                    project_id=user.current_project_id,
                    confirmed=False,
                    quantity=float(parsed.get("quantity") or 0),
                    unit=parsed.get("unit", ""),
                    unit_price=float(parsed.get("unit_price") or 0),
                    payment_type=parsed.get("payment_type", "naqd"),
                    raw_text="[chek rasmi]",
                )
            )
        await session.commit()
        count = await count_unconfirmed(session, user.id)

    await status_msg.delete()
    await message.answer(format_queued_ack(valid_items), reply_markup=daftar_reply_keyboard(count))

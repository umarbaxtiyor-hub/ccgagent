import logging
from datetime import date

from aiogram import F, Router
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import require_project
from app.handlers.day_review import format_ack_table
from app.models import Transaction, TransactionSource, TransactionType
from app.services.ai_parser import parse_receipt_image
from app.services.categories import category_names, get_or_create_category
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.photo, AllowedUser())
async def handle_receipt_photo(message: Message) -> None:
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    buffer = await message.bot.download_file(file.file_path)
    await _process_receipt_image(message, buffer.read(), "image/jpeg")


@router.message(F.document, AllowedUser())
async def handle_receipt_document(message: Message) -> None:
    """Telegram heavily compresses/downscales images sent as a regular
    "photo" - fine for a single receipt, but it turns dense multi-row
    table screenshots (20-30+ rows) blurry and causes misreads. Sending
    the same image as a "file" (document) keeps the original resolution,
    so this handles that path too for much better accuracy on big tables."""
    doc = message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await message.answer(
            "Faqat rasm (chek/jadval skrinshoti) yoki .xlsx/.csv (bank ko'chirmasi) fayllarini qabul qilaman."
        )
        return
    file = await message.bot.get_file(doc.file_id)
    buffer = await message.bot.download_file(file.file_path)
    await _process_receipt_image(message, buffer.read(), doc.mime_type)


async def _process_receipt_image(message: Message, image_bytes: bytes, media_type: str) -> None:
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

    status_msg = await message.answer("Chekni o'qiyapman...")

    try:
        parsed_items = await parse_receipt_image(
            image_bytes, media_type, expense_cats, income_cats, date.today()
        )
    except Exception as e:
        logger.exception("parse_receipt_image failed")
        await status_msg.edit_text(
            "Kechirasiz, chekni o'qiy olmadim. Iltimos, aniqroq rasm yuboring.\n"
            f"(texnik xato: {type(e).__name__}: {str(e)[:300]})"
        )
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
        project_name = user.current_project.name if user.current_project else "-"
        reporter_name = user.full_name or user.username or "Xodim"

    await status_msg.delete()
    await message.answer(format_ack_table(valid_items, project_name, reporter_name))

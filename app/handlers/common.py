import logging
from datetime import date

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.handlers.keyboards import project_list_keyboard
from app.models import Transaction, TransactionSource, TransactionType, User
from app.services.ai_parser import parse_expense_text
from app.services.categories import category_names, get_or_create_category
from app.services.projects import list_projects

logger = logging.getLogger(__name__)


async def require_project(session: AsyncSession, message: Message, user: User) -> bool:
    if user.current_project_id:
        return True

    if user.telegram_id not in settings.admin_user_id_set:
        await message.answer(
            "Sizga hali loyiha (obyekt) biriktirilmagan. /mening_id buyrug'i orqali o'z ID'ingizni oling "
            "va administratorga yuboring - u sizni kerakli loyihaga biriktiradi."
        )
        return False

    projects = await list_projects(session)
    if not projects:
        await message.answer(
            "Hali birorta loyiha (obyekt) qo'shilmagan. Iltimos, /loyiha_yarat <nomi> buyrug'i "
            "bilan birinchi loyihani qo'shing."
        )
        return False
    await message.answer(
        "Avval qaysi loyiha (obyekt) uchun ishlayotganingizni tanlang:",
        reply_markup=project_list_keyboard(projects),
    )
    return False


async def parse_and_save_transactions(
    session: AsyncSession, user: User, text: str, source: str
) -> list[dict] | str:
    """Parses text and immediately persists each valid item as an unconfirmed
    Transaction (no per-message tap-confirm) - the user reviews and confirms
    everything at once later via /kun_yakuni.

    Returns the parsed dicts (for building an acknowledgement message) on
    success, or an error message string on failure/low confidence.
    """
    expense_cats = await category_names(session, TransactionType.expense)
    income_cats = await category_names(session, TransactionType.income)

    try:
        parsed_items = await parse_expense_text(text, expense_cats, income_cats, date.today())
    except Exception:
        logger.exception("parse_expense_text failed for text=%r", text)
        return "Kechirasiz, xabaringizni tahlil qila olmadim. Iltimos, summani va nima uchunligini aniqroq yozing."

    valid_items = [p for p in parsed_items if p.get("confidence") != "low"]
    if not valid_items:
        return (
            "Xabaringizdan summa yoki tafsilotlarni aniq ajrata olmadim. Iltimos, masalan shu ko'rinishda "
            "qayta yozing: \"Sement uchun 500000 so'm to'ladim\"."
        )

    for parsed in valid_items:
        type_enum = TransactionType(parsed["type"])
        category = await get_or_create_category(session, parsed["category"], type_enum)
        session.add(
            Transaction(
                type=type_enum,
                source=TransactionSource(source),
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
                raw_text=text,
            )
        )
    await session.commit()
    return valid_items

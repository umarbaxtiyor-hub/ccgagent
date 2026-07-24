import logging
from datetime import date

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.keyboards import project_list_keyboard
from app.handlers.pending_store import PendingTransaction
from app.models import TransactionType, User
from app.services.ai_parser import parse_expense_text
from app.services.categories import category_names
from app.services.projects import list_projects

logger = logging.getLogger(__name__)


async def require_project(session: AsyncSession, message: Message, user: User) -> bool:
    if user.current_project_id:
        return True
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


async def parse_and_queue_transactions(
    session: AsyncSession, user: User, text: str, source: str
) -> list[PendingTransaction] | str:
    """Returns a non-empty list of PendingTransaction on success, or an error message string.

    Callers decide whether to register each item individually (single-item case)
    or as a batch (multi-item case) in the pending store.
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

    return [
        PendingTransaction(
            user_db_id=user.id,
            telegram_id=user.telegram_id,
            type=parsed["type"],
            amount=float(parsed["amount"]),
            category=parsed["category"],
            description=parsed.get("description", ""),
            counterparty=parsed.get("counterparty", ""),
            occurred_on=parsed["occurred_on"],
            source=source,
            project_id=user.current_project_id,
            project_name=user.current_project.name if user.current_project else None,
            full_name=user.full_name,
            quantity=float(parsed.get("quantity") or 0),
            unit=parsed.get("unit", ""),
            unit_price=float(parsed.get("unit_price") or 0),
            payment_type=parsed.get("payment_type", "naqd"),
            raw_text=text,
        )
        for parsed in valid_items
    ]

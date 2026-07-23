from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import require_project
from app.handlers.keyboards import bank_import_keyboard
from app.handlers.pending_store import (
    PendingBankImport,
    add_pending_bank,
    pop_pending_bank,
)
from app.models import Transaction, TransactionSource, TransactionType
from app.services.ai_parser import categorize_bank_rows
from app.services.bank_import import BankImportError, parse_bank_statement
from app.services.categories import category_names, get_or_create_category
from app.services.users import get_or_create_user

router = Router()

_ALLOWED_EXT = (".xlsx", ".xls", ".csv")


@router.message(F.document, AllowedUser())
async def handle_bank_statement(message: Message) -> None:
    filename = message.document.file_name or ""
    if not filename.lower().endswith(_ALLOWED_EXT):
        await message.answer("Faqat .xlsx yoki .csv formatidagi bank ko'chirmasi fayllarini qabul qilaman.")
        return

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

    file = await message.bot.get_file(message.document.file_id)
    buffer = await message.bot.download_file(file.file_path)
    file_bytes = buffer.read()

    status_msg = await message.answer("Fayl tahlil qilinmoqda...")

    try:
        rows = parse_bank_statement(file_bytes, filename)
    except BankImportError as e:
        await status_msg.edit_text(str(e))
        return
    except Exception:
        await status_msg.edit_text("Faylni o'qishda xatolik yuz berdi. Fayl formatini tekshiring.")
        return

    if len(rows) > 300:
        await status_msg.edit_text(
            f"Faylda {len(rows)} ta qator topildi, bu bir martada qayta ishlash uchun juda ko'p. "
            "Iltimos, faylni qismlarga bo'lib yuboring (masalan, oylik)."
        )
        return

    ai_input = [
        {
            "row_index": i,
            "type": r["type"].value,
            "amount": r["amount"],
            "raw_description": r["raw_description"],
        }
        for i, r in enumerate(rows)
    ]

    try:
        categorized = await categorize_bank_rows(ai_input, expense_cats, income_cats)
    except Exception:
        await status_msg.edit_text("Tranzaksiyalarni kategoriyalashda xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    total_income = sum(r["amount"] for r in rows if r["type"] == TransactionType.income)
    total_expense = sum(r["amount"] for r in rows if r["type"] == TransactionType.expense)

    enriched_rows = []
    for i, r in enumerate(rows):
        info = categorized.get(i, {})
        enriched_rows.append(
            {
                "occurred_on": r["occurred_on"].isoformat(),
                "amount": r["amount"],
                "type": r["type"].value,
                "category": info.get("category", "Boshqa xarajat"),
                "description": info.get("description", r["raw_description"]),
            }
        )

    pending = PendingBankImport(
        user_db_id=user.id,
        telegram_id=message.from_user.id,
        project_id=user.current_project_id,
        rows=enriched_rows,
    )
    pending_id = add_pending_bank(pending)

    summary = (
        f"Faylda {len(rows)} ta tranzaksiya topildi:\n"
        f"Jami kirim: {total_income:,.0f} so'm\n".replace(",", " ")
        + f"Jami chiqim: {total_expense:,.0f} so'm\n\n".replace(",", " ")
        + "Barchasini saqlaymizmi?"
    )
    await status_msg.edit_text(summary, reply_markup=bank_import_keyboard(pending_id))


@router.callback_query(F.data.startswith("bank_confirm:"))
async def confirm_bank_import(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pending = pop_pending_bank(pending_id)
    if pending is None:
        await callback.answer("Bu import muddati o'tgan.", show_alert=True)
        return

    from datetime import date as date_cls

    async with async_session() as session:
        for row in pending.rows:
            type_enum = TransactionType(row["type"])
            category = await get_or_create_category(session, row["category"], type_enum)
            session.add(
                Transaction(
                    type=type_enum,
                    source=TransactionSource.bank_statement,
                    amount=row["amount"],
                    description=row["description"],
                    counterparty="",
                    occurred_on=date_cls.fromisoformat(row["occurred_on"]),
                    category_id=category.id,
                    created_by_id=pending.user_db_id,
                    project_id=pending.project_id,
                )
            )
        await session.commit()

    await callback.message.edit_text(f"✅ {len(pending.rows)} ta tranzaksiya saqlandi.", reply_markup=None)
    await callback.answer("Saqlandi")


@router.callback_query(F.data.startswith("bank_cancel:"))
async def cancel_bank_import(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pop_pending_bank(pending_id)
    await callback.message.edit_text("❌ Import bekor qilindi.", reply_markup=None)
    await callback.answer("Bekor qilindi")

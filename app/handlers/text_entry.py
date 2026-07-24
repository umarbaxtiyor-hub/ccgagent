from datetime import date

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.common import parse_and_queue_transactions, require_project
from app.handlers.keyboards import (
    category_choice_keyboard,
    confirm_keyboard,
    format_pending,
)
from app.handlers.pending_store import get_pending_tx, pop_pending_tx
from app.models import Transaction, TransactionSource, TransactionType
from app.services.categories import category_names, get_or_create_category
from app.services.sheets import append_transaction_row
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

        result = await parse_and_queue_transactions(
            session, user, message.text, TransactionSource.manual_text.value
        )

    if isinstance(result, str):
        await message.answer(result)
        return

    for pending_id, pending in result:
        await message.answer(format_pending(pending), reply_markup=confirm_keyboard(pending_id))


@router.callback_query(F.data.startswith("tx_confirm:"))
async def confirm_transaction(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pending = pop_pending_tx(pending_id)
    if pending is None:
        await callback.answer("Bu yozuv muddati o'tgan.", show_alert=True)
        return

    type_enum = TransactionType(pending.type)
    async with async_session() as session:
        category = await get_or_create_category(session, pending.category, type_enum)
        session.add(
            Transaction(
                type=type_enum,
                source=TransactionSource(pending.source),
                amount=pending.amount,
                description=pending.description,
                counterparty=pending.counterparty,
                occurred_on=date.fromisoformat(pending.occurred_on),
                category_id=category.id,
                created_by_id=pending.user_db_id,
                project_id=pending.project_id,
            )
        )
        await session.commit()

    await append_transaction_row(
        {
            "sana": pending.occurred_on,
            "nomi": pending.description or pending.counterparty,
            "miqdor": pending.quantity or "",
            "birlik": pending.unit,
            "birim_narx": pending.unit_price or "",
            "umumiy_summa": pending.amount,
            "kategoriya": pending.category,
            "kim_yozdi": pending.full_name,
            "loyiha": pending.project_name or "",
            "tolov_turi": pending.payment_type,
            "asl_xabar": pending.raw_text,
            "izoh": pending.counterparty if pending.description else "",
        }
    )

    await callback.message.edit_text(callback.message.html_text + "\n\n✅ Saqlandi.", reply_markup=None)
    await callback.answer("Saqlandi")


@router.callback_query(F.data.startswith("tx_cancel:"))
async def cancel_transaction(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pop_pending_tx(pending_id)
    await callback.message.edit_text(callback.message.html_text + "\n\n❌ Bekor qilindi.", reply_markup=None)
    await callback.answer("Bekor qilindi")


@router.callback_query(F.data.startswith("tx_category:"))
async def choose_category(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pending = get_pending_tx(pending_id)
    if pending is None:
        await callback.answer("Bu yozuv muddati o'tgan.", show_alert=True)
        return

    async with async_session() as session:
        cats = await category_names(session, TransactionType(pending.type))

    await callback.message.edit_reply_markup(reply_markup=category_choice_keyboard(pending_id, cats))
    await callback.answer()


@router.callback_query(F.data.startswith("tx_setcat:"))
async def set_category(callback: CallbackQuery) -> None:
    _, pending_id, idx_str = callback.data.split(":", 2)
    pending = get_pending_tx(pending_id)
    if pending is None:
        await callback.answer("Bu yozuv muddati o'tgan.", show_alert=True)
        return

    async with async_session() as session:
        cats = await category_names(session, TransactionType(pending.type))
    idx = int(idx_str)
    if 0 <= idx < len(cats):
        pending.category = cats[idx]

    await callback.message.edit_text(format_pending(pending), reply_markup=confirm_keyboard(pending_id))
    await callback.answer()


@router.callback_query(F.data.startswith("tx_back:"))
async def back_to_confirm(callback: CallbackQuery) -> None:
    pending_id = callback.data.split(":", 1)[1]
    pending = get_pending_tx(pending_id)
    if pending is None:
        await callback.answer("Bu yozuv muddati o'tgan.", show_alert=True)
        return
    await callback.message.edit_text(format_pending(pending), reply_markup=confirm_keyboard(pending_id))
    await callback.answer()

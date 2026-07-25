import logging
from collections import defaultdict
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.access import AllowedUser
from app.config import settings
from app.db import async_session
from app.handlers.keyboards import day_category_choice_keyboard, day_review_keyboard, format_day_review
from app.models import Transaction
from app.services.categories import category_names, get_or_create_category
from app.services.sheets import append_transaction_row
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


def _fmt_money(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


def format_daily_text_report(rows: list[dict], reporter_name: str) -> str:
    """Plain-text daily report for the CEO: per project, kirim/chiqim/balans
    plus the expense list (nomi, hajmi, birim narx, jami narx, izoh)."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row.get("loyiha") or "-"].append(row)

    lines = [f"📋 <b>Kunlik hisobot</b> - {date.today().isoformat()}", f"👤 Kim: {reporter_name}"]

    for project_name, project_rows in by_project.items():
        expense_rows = [r for r in project_rows if r["_type"] == "expense"]
        income_rows = [r for r in project_rows if r["_type"] == "income"]
        total_expense = sum(r["umumiy_summa"] for r in expense_rows)
        total_income = sum(r["umumiy_summa"] for r in income_rows)
        balance = total_income - total_expense

        lines.append("")
        lines.append(f"🏗 <b>Loyiha: {project_name}</b>")
        lines.append(f"💰 Kirim: {_fmt_money(total_income)} so'm")
        lines.append(f"💸 Chiqim: {_fmt_money(total_expense)} so'm")
        lines.append(f"⚖️ Balans: {_fmt_money(balance)} so'm")

        if expense_rows:
            lines.append("\n<b>Xarajatlar ro'yxati:</b>")
            for i, r in enumerate(expense_rows, start=1):
                name = r.get("nomi") or "-"
                qty = r.get("miqdor") or ""
                unit = r.get("birlik") or ""
                unit_price = r.get("birim_narx") or ""
                total_str = _fmt_money(r["umumiy_summa"])
                lines.append(f"{i}. {name} — {total_str} so'm")
                if qty and unit_price:
                    qty_part = f"{qty:g} {unit}".strip()
                    lines.append(f"    {qty_part} x {_fmt_money(unit_price)} so'm")
                if r.get("izoh"):
                    lines.append(f"    ({r['izoh']})")

        if income_rows:
            lines.append("\n<b>Kirimlar ro'yxati:</b>")
            for i, r in enumerate(income_rows, start=1):
                name = r.get("nomi") or "-"
                total_str = _fmt_money(r["umumiy_summa"])
                lines.append(f"{i}. {name} — {total_str} so'm")
                if r.get("izoh"):
                    lines.append(f"    ({r['izoh']})")

    return "\n".join(lines)


async def _unconfirmed_for_user(session: AsyncSession, user_id: int) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.created_by_id == user_id, Transaction.confirmed.is_(False))
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.created_by),
            selectinload(Transaction.project),
        )
        .order_by(Transaction.created_at)
    )
    return list(result.scalars().all())


async def _render_day_list(
    session: AsyncSession, user_id: int, page: int = 0
) -> tuple[str, InlineKeyboardMarkup | None]:
    transactions = await _unconfirmed_for_user(session, user_id)
    if not transactions:
        return "Tasdiqlanmagan yozuvlar yo'q.", None
    return format_day_review(transactions, page), day_review_keyboard(transactions, page)


@router.message(Command("kun_yakuni"), AllowedUser())
async def cmd_kun_yakuni(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        text, markup = await _render_day_list(session, user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("day_page:"))
async def change_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        text, markup = await _render_day_list(session, user.id, page)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("day_list:"))
async def show_day_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        text, markup = await _render_day_list(session, user.id, page)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("day_cat:"))
async def choose_category(callback: CallbackQuery) -> None:
    _, tx_id_str, page_str = callback.data.split(":", 2)
    tx_id, page = int(tx_id_str), int(page_str)
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        tx = await session.get(Transaction, tx_id)
        if tx is None or tx.confirmed or tx.created_by_id != user.id:
            await callback.answer("Bu yozuv topilmadi.", show_alert=True)
            return
        cats = await category_names(session, tx.type)

    await callback.message.edit_reply_markup(reply_markup=day_category_choice_keyboard(tx_id, cats, page))
    await callback.answer()


@router.callback_query(F.data.startswith("day_setcat:"))
async def set_category(callback: CallbackQuery) -> None:
    _, tx_id_str, idx_str, page_str = callback.data.split(":", 3)
    tx_id, page = int(tx_id_str), int(page_str)
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        tx = await session.get(Transaction, tx_id)
        if tx is None or tx.confirmed or tx.created_by_id != user.id:
            await callback.answer("Bu yozuv topilmadi.", show_alert=True)
            return

        cats = await category_names(session, tx.type)
        idx = int(idx_str)
        if 0 <= idx < len(cats):
            category = await get_or_create_category(session, cats[idx], tx.type)
            tx.category_id = category.id
        await session.commit()

        text, markup = await _render_day_list(session, user.id, page)

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("Kategoriya yangilandi")


@router.callback_query(F.data.startswith("day_del:"))
async def delete_item(callback: CallbackQuery) -> None:
    _, tx_id_str, page_str = callback.data.split(":", 2)
    tx_id, page = int(tx_id_str), int(page_str)
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        tx = await session.get(Transaction, tx_id)
        if tx is not None and not tx.confirmed and tx.created_by_id == user.id:
            await session.delete(tx)
            await session.commit()

        text, markup = await _render_day_list(session, user.id, page)

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("O'chirildi")


@router.callback_query(F.data == "day_confirm_all")
async def confirm_all(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        transactions = await _unconfirmed_for_user(session, user.id)
        if not transactions:
            await callback.answer("Tasdiqlanadigan yozuv yo'q.", show_alert=True)
            return

        rows = []
        occurred_dates = []
        for t in transactions:
            t.confirmed = True
            occurred_dates.append(t.occurred_on)
            rows.append(
                {
                    "_type": t.type.value,
                    "sana": t.occurred_on.isoformat(),
                    "nomi": t.description or t.counterparty,
                    "miqdor": float(t.quantity) or "",
                    "birlik": t.unit,
                    "birim_narx": float(t.unit_price) or "",
                    "umumiy_summa": float(t.amount),
                    "kategoriya": t.category.name if t.category else "",
                    "kim_yozdi": t.created_by.full_name if t.created_by else "",
                    "loyiha": t.project.name if t.project else "",
                    "tolov_turi": t.payment_type,
                    "asl_xabar": t.raw_text,
                    "izoh": t.counterparty if t.description else "",
                }
            )
        await session.commit()

        reporter_name = user.full_name or user.username or "Xodim"

    for row in rows:
        sheet_row = {k: v for k, v in row.items() if k != "_type"}
        await append_transaction_row(sheet_row)

    await callback.message.edit_text(
        f"✅ {len(rows)} ta yozuv tasdiqlandi va Google Sheetga yuborildi.", reply_markup=None
    )
    await callback.answer("Tasdiqlandi")

    if settings.report_recipient_id:
        try:
            recipient_id = int(settings.report_recipient_id)
            report_text = format_daily_text_report(rows, reporter_name)
            await callback.bot.send_message(chat_id=recipient_id, text=report_text)
        except Exception:
            logger.exception("Failed to send daily report to recipient")


@router.callback_query(F.data == "day_cancel_all")
async def cancel_all(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        transactions = await _unconfirmed_for_user(session, user.id)
        count = len(transactions)
        for t in transactions:
            await session.delete(t)
        await session.commit()

    await callback.message.edit_text(f"❌ {count} ta yozuv bekor qilindi.", reply_markup=None)
    await callback.answer("Bekor qilindi")

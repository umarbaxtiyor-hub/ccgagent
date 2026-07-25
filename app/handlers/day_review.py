import logging
from collections import defaultdict
from datetime import date
from html import escape as h

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.access import AllowedUser
from app.config import settings
from app.db import async_session
from app.handlers.keyboards import (
    daftar_reply_keyboard,
    day_category_choice_keyboard,
    day_review_keyboard,
    day_row_picker_keyboard,
)
from app.models import Transaction
from app.services.categories import category_names, get_or_create_category
from app.services.sheets import append_transaction_row
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


def _fmt_amount(amount: float) -> str:
    return f"{amount:,.0f}"


_CAT_WIDTH = 11
_NAME_WIDTH = 10
_SEP = "-" * (3 + _CAT_WIDTH + _NAME_WIDTH + 6 + 1 + 10)


def _table_row(idx: int, category: str, name: str, qty: float, amount: float) -> str:
    display_cat = h(category)[:_CAT_WIDTH]
    display_name = h(name)[:_NAME_WIDTH]
    qty_str = f"({qty:g}x)" if qty else "-"
    return (
        f"{idx:02d} {display_cat:<{_CAT_WIDTH}}{display_name:<{_NAME_WIDTH}}"
        f"{qty_str:>6} {_fmt_amount(amount):>10}"
    )


def _build_table(items: list[tuple[str, str, float, float, str]]) -> list[str]:
    """items: (category, name, qty, amount, type) where type is 'income'/'expense'."""
    header = (
        f"{'№':<3}{'Kategoriya':<{_CAT_WIDTH}}{'Nomi':<{_NAME_WIDTH}}{'Miqdor':>6} {'Summa':>10}"
    )
    table_lines = [_SEP, header, _SEP]
    total_income = 0.0
    total_expense = 0.0
    for i, (category, name, qty, amount, type_) in enumerate(items, start=1):
        table_lines.append(_table_row(i, category, name, qty, amount))
        if type_ == "income":
            total_income += amount
        else:
            total_expense += amount
    table_lines.append(_SEP)
    table_lines.append(f"{'Jami kirim:':<27}{_fmt_amount(total_income):>8} UZS")
    table_lines.append(f"{'JAMI CHIQIM:':<27}{_fmt_amount(total_expense):>8} UZS")
    table_lines.append(_SEP)
    table_lines.append(f"{'BALANS:':<27}{_fmt_amount(total_income - total_expense):>8} UZS")
    return table_lines


def _project_header(project_name: str, reporter_name: str) -> str:
    today_str = date.today().strftime("%d.%m.%Y")
    return f"📋 LOYIHA: {h(project_name)}\n👤 XODIM: {h(reporter_name)}\n📅 SANA: {today_str}"


def format_daily_text_report(rows: list[dict], reporter_name: str) -> str:
    """Monospace, receipt-style daily report for the CEO: one block per
    project with a Nomi/Miqdor/Summa table and kirim/chiqim/balans totals."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row.get("loyiha") or "-"].append(row)

    sections = []
    for project_name, project_rows in by_project.items():
        items = [
            (r.get("kategoriya") or "-", r.get("nomi") or "-", r.get("miqdor") or 0, r["umumiy_summa"], r["_type"])
            for r in sorted(project_rows, key=lambda r: 0 if r["_type"] == "expense" else 1)
        ]
        table = "<pre>" + "\n".join(_build_table(items)) + "</pre>"
        sections.append(_project_header(project_name, reporter_name) + "\n\n" + table)

    return "\n\n".join(sections)


def format_day_review(transactions: list[Transaction]) -> str:
    """Same receipt-style table as the CEO report, for the Daftar view."""
    if not transactions:
        return "Tasdiqlanmagan yozuvlar yo'q."

    by_project: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        by_project[t.project.name if t.project else "-"].append(t)
    reporter_name = transactions[0].created_by.full_name if transactions[0].created_by else ""

    sections = []
    for project_name, items in by_project.items():
        table_items = [
            (
                t.category.name if t.category else "-",
                t.description or t.counterparty or "-",
                float(t.quantity or 0),
                float(t.amount),
                t.type.value,
            )
            for t in items
        ]
        table = "<pre>" + "\n".join(_build_table(table_items)) + "</pre>"
        sections.append(_project_header(project_name, reporter_name) + "\n\n" + table)

    return "\n\n".join(sections)


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


async def _render_day_list(session: AsyncSession, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    transactions = await _unconfirmed_for_user(session, user_id)
    if not transactions:
        return "Tasdiqlanmagan yozuvlar yo'q.", None
    text = format_day_review(transactions) + "\n\nTahrirlash yoki o'chirish uchun tugmani bosing."
    return text, day_review_keyboard()


async def _open_daftar(session: AsyncSession, telegram_id: int, full_name: str, username: str) -> tuple:
    user = await get_or_create_user(session, telegram_id=telegram_id, full_name=full_name, username=username)
    return await _render_day_list(session, user.id)


@router.message(Command("daftar", "kun_yakuni"), AllowedUser())
async def cmd_daftar(message: Message) -> None:
    async with async_session() as session:
        text, markup = await _open_daftar(
            session, message.from_user.id, message.from_user.full_name, message.from_user.username or ""
        )
    await message.answer(text, reply_markup=markup)


@router.message(F.text.startswith("📒 Daftar"), AllowedUser())
async def open_daftar_button(message: Message) -> None:
    async with async_session() as session:
        text, markup = await _open_daftar(
            session, message.from_user.id, message.from_user.full_name, message.from_user.username or ""
        )
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "day_list")
async def show_day_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await _open_daftar(
            session, callback.from_user.id, callback.from_user.full_name, callback.from_user.username or ""
        )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "day_edit_prompt")
async def edit_prompt(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        transactions = await _unconfirmed_for_user(session, user.id)

    if not transactions:
        await callback.answer("Tasdiqlanmagan yozuvlar yo'q.", show_alert=True)
        return

    text = format_day_review(transactions) + "\n\n<b>O'zgartiriladigan yozuv raqamini tanlang.</b>"
    await callback.message.edit_text(text, reply_markup=day_row_picker_keyboard(transactions, "edit"))
    await callback.answer()


@router.callback_query(F.data == "day_delete_prompt")
async def delete_prompt(callback: CallbackQuery) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        transactions = await _unconfirmed_for_user(session, user.id)

    if not transactions:
        await callback.answer("Tasdiqlanmagan yozuvlar yo'q.", show_alert=True)
        return

    text = format_day_review(transactions) + "\n\n<b>O'chiriladigan yozuv raqamini tanlang.</b>"
    await callback.message.edit_text(text, reply_markup=day_row_picker_keyboard(transactions, "del"))
    await callback.answer()


@router.callback_query(F.data.startswith("day_pick_edit:"))
async def choose_category(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":", 1)[1])
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

    await callback.message.edit_reply_markup(reply_markup=day_category_choice_keyboard(tx_id, cats))
    await callback.answer()


@router.callback_query(F.data.startswith("day_setcat:"))
async def set_category(callback: CallbackQuery) -> None:
    _, tx_id_str, idx_str = callback.data.split(":", 2)
    tx_id = int(tx_id_str)
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

        text, markup = await _render_day_list(session, user.id)

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("Kategoriya yangilandi")


@router.callback_query(F.data.startswith("day_pick_del:"))
async def delete_item(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":", 1)[1])
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

        text, markup = await _render_day_list(session, user.id)

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
    await callback.message.answer("📒 Daftar bo'sh.", reply_markup=daftar_reply_keyboard(0))

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
    await callback.message.answer("📒 Daftar bo'sh.", reply_markup=daftar_reply_keyboard(0))

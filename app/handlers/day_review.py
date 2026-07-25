import logging
from collections import defaultdict
from datetime import date
from html import escape as h

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
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
    day_review_keyboard,
    day_row_picker_keyboard,
)
from app.models import Transaction
from app.services.sheets import append_transaction_row
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


def _fmt_amount(amount: float) -> str:
    return f"{amount:,.0f}"


_NAME_WIDTH = 16
_UNIT_WIDTH = 5
_SEP = "-" * (3 + _NAME_WIDTH + 5 + 1 + _UNIT_WIDTH + 1 + 10)


def _table_row(idx: int, name: str, qty: float, unit: str, amount: float) -> str:
    display_name = h(name)[:_NAME_WIDTH]
    qty_str = f"{qty:g}" if qty else "-"
    display_unit = h(unit)[:_UNIT_WIDTH]
    return (
        f"{idx:02d} {display_name:<{_NAME_WIDTH}}"
        f"{qty_str:>5} {display_unit:<{_UNIT_WIDTH}}{_fmt_amount(amount):>10}"
    )


def _build_table(items: list[tuple[str, float, str, float, str]]) -> list[str]:
    """items: (name, qty, unit, amount, type) where type is 'income'/'expense'."""
    header = (
        f"{'№':<3}{'Nomi':<{_NAME_WIDTH}}"
        f"{'Miqd':>5} {'Birl':<{_UNIT_WIDTH}}{'Summa':>10}"
    )
    table_lines = [_SEP, header, _SEP]
    total_income = 0.0
    total_expense = 0.0
    for i, (name, qty, unit, amount, type_) in enumerate(items, start=1):
        table_lines.append(_table_row(i, name, qty, unit, amount))
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
    return f"📋 LOYIHA: {h(project_name)}\n👤 XODIM: {h(reporter_name)}"


def _date_block(date_str: str, items: list[tuple[str, float, str, float, str]]) -> str:
    table = "<pre>" + "\n".join(_build_table(items)) + "</pre>"
    return f"📅 SANA: {date_str}\n" + table


def format_daily_text_report(rows: list[dict], reporter_name: str) -> str:
    """Monospace, receipt-style daily report for the CEO: one block per
    project, each split by day so kirim/chiqim/balans are per-day totals."""
    by_project: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_project[row.get("loyiha") or "-"].append(row)

    sections = []
    for project_name, project_rows in by_project.items():
        by_date: dict[str, list[dict]] = defaultdict(list)
        for r in project_rows:
            by_date[r["sana"]].append(r)

        date_blocks = []
        for sana in sorted(by_date):
            date_rows = sorted(by_date[sana], key=lambda r: 0 if r["_type"] == "expense" else 1)
            items = [
                (r.get("nomi") or r.get("kategoriya") or "-", r.get("miqdor") or 0, r.get("birlik") or "", r["umumiy_summa"], r["_type"])
                for r in date_rows
            ]
            date_str = date.fromisoformat(sana).strftime("%d.%m.%Y")
            date_blocks.append(_date_block(date_str, items))

        sections.append(_project_header(project_name, reporter_name) + "\n\n" + "\n\n".join(date_blocks))

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
        by_date: dict[date, list[Transaction]] = defaultdict(list)
        for t in items:
            by_date[t.occurred_on].append(t)

        date_blocks = []
        for occurred_on in sorted(by_date):
            table_items = [
                (
                    t.description or t.counterparty or (t.category.name if t.category else "-"),
                    float(t.quantity or 0),
                    t.unit or "",
                    float(t.amount),
                    t.type.value,
                )
                for t in by_date[occurred_on]
            ]
            date_blocks.append(_date_block(occurred_on.strftime("%d.%m.%Y"), table_items))

        sections.append(_project_header(project_name, reporter_name) + "\n\n" + "\n\n".join(date_blocks))

    return "\n\n".join(sections)


def format_ack_table(items: list[dict], project_name: str, reporter_name: str, editable: bool = False) -> str:
    """Short plain acknowledgement shown right after a message is parsed.
    Deliberately NOT the heavy receipt-style table - that design made users
    think this bot message itself was what they should long-press to edit,
    which doesn't work (Telegram only lets you edit your own messages).
    Reviewing, editing and confirming all happen from /daftar instead."""
    lines = []
    total = 0.0
    for p in items:
        name = h(p.get("description") or p["category"])
        amount = float(p["amount"])
        sign = "-" if p["type"] == "expense" else "+"
        total += -amount if p["type"] == "expense" else amount
        lines.append(f"• {name} — {sign}{_fmt_amount(amount)} so'm")
    total_line = f"Jami: {_fmt_amount(total)} so'm"
    hint = (
        "To'g'irlash uchun shu xabaringizni tahrirlang (uzoq bosib \"Edit\"), yoki 📒 Daftar orqali."
        if editable
        else "Ko'rish, to'g'irlash va tasdiqlash uchun 📒 Daftar."
    )
    return (
        "✅ Qabul qilindi (tasdiqlash kutilmoqda)\n\n"
        + "\n".join(lines)
        + f"\n\n{total_line}\n\n{hint}"
    )


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


@router.callback_query(F.data == "ack_goto_daftar")
async def ack_goto_daftar(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await _open_daftar(
            session, callback.from_user.id, callback.from_user.full_name, callback.from_user.username or ""
        )
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


_EDIT_HINT = (
    "Xabaringizni to'g'irlash uchun: o'zingiz yozgan xabar ustiga bosib turing va "
    "\"Tahrirlash\"/\"Edit\"ni tanlang, kerakli joyini o'zgartirib qayta yuboring."
)


@router.callback_query(F.data == "ack_edit_hint")
async def ack_edit_hint(callback: CallbackQuery) -> None:
    await callback.answer(_EDIT_HINT, show_alert=True)


@router.callback_query(F.data == "day_edit_hint")
async def day_edit_hint(callback: CallbackQuery) -> None:
    await callback.answer(_EDIT_HINT, show_alert=True)


@router.callback_query(F.data.in_({"day_list", "day_refresh"}))
async def show_day_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await _open_daftar(
            session, callback.from_user.id, callback.from_user.full_name, callback.from_user.username or ""
        )
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer("Yangilandi" if callback.data == "day_refresh" else None)


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
            if t.quantity and not t.unit_price:
                t.unit_price = float(t.amount) / float(t.quantity)
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

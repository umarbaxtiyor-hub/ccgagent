from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.handlers.pending_store import PendingTransaction
from app.models import Project


def confirm_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Tasdiqlash", callback_data=f"tx_confirm:{pending_id}"),
                InlineKeyboardButton(text="Kategoriya", callback_data=f"tx_category:{pending_id}"),
            ],
            [InlineKeyboardButton(text="Bekor qilish", callback_data=f"tx_cancel:{pending_id}")],
        ]
    )


def category_choice_keyboard(pending_id: str, categories: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        chunk = categories[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(text=name, callback_data=f"tx_setcat:{pending_id}:{idx}")
                for idx, name in zip(range(i, i + len(chunk)), chunk)
            ]
        )
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data=f"tx_back:{pending_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def batch_confirm_keyboard(batch_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Barchasini tasdiqlash", callback_data=f"txb_confirm:{batch_id}")],
            [InlineKeyboardButton(text="Bekor qilish", callback_data=f"txb_cancel:{batch_id}")],
        ]
    )


def bank_import_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Barchasini saqlash", callback_data=f"bank_confirm:{pending_id}"),
                InlineKeyboardButton(text="Bekor qilish", callback_data=f"bank_cancel:{pending_id}"),
            ]
        ]
    )


def project_list_keyboard(projects: list[Project]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(projects), 2):
        chunk = projects[i : i + 2]
        rows.append(
            [InlineKeyboardButton(text=p.name, callback_data=f"proj_select:{p.id}") for p in chunk]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Bugun", callback_data="report:today"),
                InlineKeyboardButton(text="Shu hafta", callback_data="report:week"),
                InlineKeyboardButton(text="Shu oy", callback_data="report:month"),
            ]
        ]
    )


def format_pending(p: PendingTransaction) -> str:
    type_label = "Kirim" if p.type == "income" else "Chiqim"
    lines = [
        f"<b>{type_label}</b>: {p.amount:,.0f} so'm".replace(",", " "),
        f"Loyiha: {p.project_name or '-'}",
        f"Kategoriya: {p.category}",
        f"Sana: {p.occurred_on}",
        f"Tavsif: {p.description or '-'}",
    ]
    if p.counterparty:
        lines.append(f"Kontragent: {p.counterparty}")
    lines.append("\nTasdiqlaysizmi?")
    return "\n".join(lines)


def format_pending_batch(items: list[PendingTransaction]) -> str:
    lines = [f"<b>{len(items)} ta yozuv topildi</b> (Loyiha: {items[0].project_name or '-'}):\n"]
    total_expense = 0.0
    total_income = 0.0
    for i, p in enumerate(items, start=1):
        type_label = "Kirim" if p.type == "income" else "Chiqim"
        amount_str = f"{p.amount:,.0f}".replace(",", " ")
        line = f"{i}. {type_label}: {amount_str} so'm - {p.category}"
        if p.description:
            line += f" ({p.description})"
        lines.append(line)
        if p.type == "income":
            total_income += p.amount
        else:
            total_expense += p.amount

    lines.append("")
    if total_expense:
        lines.append(f"Jami chiqim: {total_expense:,.0f} so'm".replace(",", " "))
    if total_income:
        lines.append(f"Jami kirim: {total_income:,.0f} so'm".replace(",", " "))
    lines.append("\nBarchasini tasdiqlaysizmi?")
    return "\n".join(lines)

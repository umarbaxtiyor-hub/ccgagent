from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.handlers.pending_store import PendingTransaction


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


def bank_import_keyboard(pending_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Barchasini saqlash", callback_data=f"bank_confirm:{pending_id}"),
                InlineKeyboardButton(text="Bekor qilish", callback_data=f"bank_cancel:{pending_id}"),
            ]
        ]
    )


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
        f"Kategoriya: {p.category}",
        f"Sana: {p.occurred_on}",
        f"Tavsif: {p.description or '-'}",
    ]
    if p.counterparty:
        lines.append(f"Kontragent: {p.counterparty}")
    lines.append("\nTasdiqlaysizmi?")
    return "\n".join(lines)

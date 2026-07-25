from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import Project, Transaction


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


def format_queued_ack(items: list[dict]) -> str:
    """Lightweight acknowledgement shown right after a message is parsed and
    saved as unconfirmed - no buttons, review happens later via /kun_yakuni."""
    multi = len(items) > 1
    lines = [f"✅ Qabul qilindi ({len(items)} ta yozuv, tasdiqlash kutilmoqda):\n" if multi else "✅ Qabul qilindi (tasdiqlash kutilmoqda):\n"]
    for i, p in enumerate(items, start=1):
        type_label = "Kirim" if p["type"] == "income" else "Chiqim"
        amount_str = f"{float(p['amount']):,.0f}".replace(",", " ")
        prefix = f"{i}. " if multi else ""
        line = f"{prefix}{type_label}: {amount_str} so'm - {p['category']}"
        if p.get("description"):
            line += f" ({p['description']})"
        lines.append(line)
    lines.append("\nKun oxirida /kun_yakuni bilan ko'rib chiqib, tasdiqlang.")
    return "\n".join(lines)


def format_day_review(transactions: list[Transaction]) -> str:
    lines = [f"<b>{len(transactions)} ta tasdiqlanmagan yozuv:</b>\n"]
    total_expense = 0.0
    total_income = 0.0
    for i, t in enumerate(transactions, start=1):
        type_label = "Kirim" if t.type.value == "income" else "Chiqim"
        amount = float(t.amount)
        amount_str = f"{amount:,.0f}".replace(",", " ")
        line = f"{i}. {t.occurred_on.isoformat()} - {type_label}: {amount_str} so'm"
        if t.description:
            line += f" - {t.description}"
        lines.append(line)
        if t.type.value == "income":
            total_income += amount
        else:
            total_expense += amount

    lines.append("")
    if total_expense:
        lines.append(f"Jami chiqim: {total_expense:,.0f} so'm".replace(",", " "))
    if total_income:
        lines.append(f"Jami kirim: {total_income:,.0f} so'm".replace(",", " "))
    lines.append("\nHar bir yozuvni tahrirlash (✏️) yoki o'chirish (🗑) mumkin, aks holda barchasini tasdiqlang.")
    return "\n".join(lines)


def day_review_keyboard(transactions: list[Transaction]) -> InlineKeyboardMarkup:
    rows = []
    for i, t in enumerate(transactions, start=1):
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ {i}", callback_data=f"day_cat:{t.id}"),
                InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"day_del:{t.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="✅ Barchasini tasdiqlash", callback_data="day_confirm_all")])
    rows.append([InlineKeyboardButton(text="❌ Hammasini bekor qilish", callback_data="day_cancel_all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def day_category_choice_keyboard(tx_id: int, categories: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        chunk = categories[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(text=name, callback_data=f"day_setcat:{tx_id}:{idx}")
                for idx, name in zip(range(i, i + len(chunk)), chunk)
            ]
        )
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data="day_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

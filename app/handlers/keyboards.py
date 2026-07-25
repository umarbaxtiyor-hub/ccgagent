from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

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


def new_user_assign_keyboard(employee_telegram_id: int, projects: list[Project]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(projects), 2):
        chunk = projects[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(
                    text=p.name, callback_data=f"newuser_assign:{employee_telegram_id}:{p.id}"
                )
                for p in chunk
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Bugun", callback_data="report:today"),
                InlineKeyboardButton(text="Shu hafta", callback_data="report:week"),
                InlineKeyboardButton(text="Shu oy", callback_data="report:month"),
            ],
            [InlineKeyboardButton(text="Hammasi (boshidan)", callback_data="report:all")],
        ]
    )


def format_queued_ack(items: list[dict]) -> str:
    """Lightweight acknowledgement shown right after a message is parsed and
    saved as unconfirmed - no buttons, review happens later via /daftar."""
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
    lines.append("\nKo'rib chiqish/tasdiqlash uchun pastdagi \"📒 Daftar\" tugmasini bosing.")
    return "\n".join(lines)


def daftar_reply_keyboard(count: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"📒 Daftar ({count})")]],
        resize_keyboard=True,
    )


def format_day_review(transactions: list[Transaction]) -> str:
    lines = [f"📒 <b>Daftar</b> ({len(transactions)} ta yozuv):\n"]

    for i, t in enumerate(transactions, start=1):
        type_label = "Kirim" if t.type.value == "income" else "Chiqim"
        amount = float(t.amount)
        amount_str = f"{amount:,.0f}".replace(",", " ")
        line = f"{i}. {t.occurred_on.isoformat()} - {type_label}: {amount_str} so'm"
        if t.description:
            line += f" - {t.description}"
        lines.append(line)

    total_expense = sum(float(t.amount) for t in transactions if t.type.value == "expense")
    total_income = sum(float(t.amount) for t in transactions if t.type.value == "income")

    lines.append("")
    if total_expense:
        lines.append(f"Jami chiqim: {total_expense:,.0f} so'm".replace(",", " "))
    if total_income:
        lines.append(f"Jami kirim: {total_income:,.0f} so'm".replace(",", " "))
    lines.append("\nTahrirlash yoki o'chirish uchun tugmani bosing.")
    return "\n".join(lines)


def day_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="day_edit_prompt"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data="day_delete_prompt"),
            ],
            [InlineKeyboardButton(text="✅ Hammasini tasdiqlash", callback_data="day_confirm_all")],
            [InlineKeyboardButton(text="🗑 Tozalash", callback_data="day_cancel_all")],
        ]
    )


def day_row_picker_keyboard(transactions: list[Transaction], action: str) -> InlineKeyboardMarkup:
    """Compact numbered grid so the user can pick which row to edit/delete
    without one button-pair per row cluttering the screen."""
    rows = []
    chunk_size = 5
    for i in range(0, len(transactions), chunk_size):
        chunk = transactions[i : i + chunk_size]
        rows.append(
            [
                InlineKeyboardButton(text=str(i + offset + 1), callback_data=f"day_pick_{action}:{t.id}")
                for offset, t in enumerate(chunk)
            ]
        )
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data="day_list")])
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

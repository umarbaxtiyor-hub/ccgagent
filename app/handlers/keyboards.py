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


DAY_PAGE_SIZE = 8


def _total_pages(count: int, page_size: int = DAY_PAGE_SIZE) -> int:
    return max(1, (count + page_size - 1) // page_size)


def format_day_review(transactions: list[Transaction], page: int = 0, page_size: int = DAY_PAGE_SIZE) -> str:
    total = len(transactions)
    total_pages = _total_pages(total, page_size)
    start = page * page_size
    page_items = transactions[start : start + page_size]

    header = f"<b>{total} ta tasdiqlanmagan yozuv</b>"
    if total_pages > 1:
        header += f" (sahifa {page + 1}/{total_pages})"
    lines = [header + ":\n"]

    for offset, t in enumerate(page_items):
        i = start + offset + 1
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
    lines.append("\nHar bir yozuvni tahrirlash (✏️) yoki o'chirish (🗑) mumkin, aks holda barchasini tasdiqlang.")
    return "\n".join(lines)


def day_review_keyboard(
    transactions: list[Transaction], page: int = 0, page_size: int = DAY_PAGE_SIZE
) -> InlineKeyboardMarkup:
    total_pages = _total_pages(len(transactions), page_size)
    start = page * page_size
    page_items = transactions[start : start + page_size]

    rows = []
    for offset, t in enumerate(page_items):
        i = start + offset + 1
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ {i}", callback_data=f"day_cat:{t.id}:{page}"),
                InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"day_del:{t.id}:{page}"),
            ]
        )

    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"day_page:{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"day_page:{page + 1}"))
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="✅ Barchasini tasdiqlash", callback_data="day_confirm_all")])
    rows.append([InlineKeyboardButton(text="❌ Hammasini bekor qilish", callback_data="day_cancel_all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def day_category_choice_keyboard(tx_id: int, categories: list[str], page: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        chunk = categories[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(text=name, callback_data=f"day_setcat:{tx_id}:{idx}:{page}")
                for idx, name in zip(range(i, i + len(chunk)), chunk)
            ]
        )
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data=f"day_list:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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


def ack_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="ack_edit")]]
    )


def correction_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ack_cancel_edit")]]
    )


def daftar_reply_keyboard(count: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"📒 Daftar ({count})")]],
        resize_keyboard=True,
    )


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

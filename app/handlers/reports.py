from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.keyboards import report_period_keyboard
from app.services.excel_export import build_report

router = Router()

_PERIOD_LABELS = {"today": "Bugungi", "week": "Shu haftalik", "month": "Shu oylik", "all": "Boshidan hozirgacha"}


def _period_range(period: str) -> tuple[date | None, date]:
    today = date.today()
    if period == "today":
        return today, today
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return today.replace(day=1), today
    if period == "all":
        return None, today
    raise ValueError(period)


@router.message(Command("report"), AllowedUser())
async def cmd_report(message: Message) -> None:
    await message.answer("Qaysi davr uchun hisobot kerak?", reply_markup=report_period_keyboard())


@router.callback_query(F.data.startswith("report:"))
async def send_report(callback: CallbackQuery) -> None:
    period = callback.data.split(":", 1)[1]
    start, end = _period_range(period)

    async with async_session() as session:
        buffer = await build_report(session, start, end)

    start_label = start.isoformat() if start else "boshidan"
    filename = f"hisobot_{start_label}_{end.isoformat()}.xlsx"
    await callback.message.answer_document(
        BufferedInputFile(buffer.read(), filename=filename),
        caption=f"{_PERIOD_LABELS[period]} hisobot ({start_label} - {end.isoformat()})",
    )
    await callback.answer()

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import async_session
from app.handlers.day_review import format_daily_text_report, transaction_to_row
from app.models import Transaction

logger = logging.getLogger(__name__)

# Uzbekistan has used a fixed UTC+5 offset year-round since 1992 (no DST),
# so a plain fixed-offset timezone is simpler and more robust here than
# depending on a system/tzdata "Asia/Tashkent" zoneinfo entry being present.
_TASHKENT = timezone(timedelta(hours=5))
_DIGEST_HOUR = 21


async def _confirmed_rows_for_date(target_date) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.confirmed.is_(True), Transaction.occurred_on == target_date)
            .options(
                selectinload(Transaction.category),
                selectinload(Transaction.created_by),
                selectinload(Transaction.project),
            )
        )
        transactions = list(result.scalars().all())
    return [transaction_to_row(t) for t in transactions]


async def run_daily_ceo_digest(bot: Bot) -> None:
    """Runs forever, sending one consolidated report to REPORT_RECIPIENT_ID
    every day at 21:00 Tashkent time, covering that day's confirmed
    transactions across all employees/projects - replaces the old behavior
    of pinging the recipient separately every time an employee confirmed."""
    if not settings.report_recipient_id:
        return

    while True:
        now = datetime.now(_TASHKENT)
        target = now.replace(hour=_DIGEST_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        try:
            rows = await _confirmed_rows_for_date(target.date())
            if not rows:
                continue
            report_text = format_daily_text_report(rows)
            recipient_id = int(settings.report_recipient_id)
            await bot.send_message(chat_id=recipient_id, text=report_text)
        except Exception:
            logger.exception("Failed to send nightly CEO digest")

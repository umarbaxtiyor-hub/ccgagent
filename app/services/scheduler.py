import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape as h

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import async_session
from app.handlers.day_review import format_project_report_messages, transaction_to_row
from app.models import Transaction

logger = logging.getLogger(__name__)

# Uzbekistan has used a fixed UTC+5 offset year-round since 1992 (no DST),
# so a plain fixed-offset timezone is simpler and more robust here than
# depending on a system/tzdata "Asia/Tashkent" zoneinfo entry being present.
_TASHKENT = timezone(timedelta(hours=5))
_DIGEST_HOUR = 20
_REMINDER_HOUR, _REMINDER_MINUTE = 19, 30


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


async def _pending_users_for_date(target_date) -> list[dict]:
    """Employees who still have unconfirmed Daftar entries for target_date -
    these are silently excluded from that day's digest once it fires, since
    the digest only ever looks at each date once."""
    async with async_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.confirmed.is_(False), Transaction.occurred_on == target_date)
            .options(selectinload(Transaction.created_by), selectinload(Transaction.project))
        )
        transactions = list(result.scalars().all())

    by_user: dict[int, dict] = {}
    for t in transactions:
        if not t.created_by:
            continue
        entry = by_user.setdefault(
            t.created_by.telegram_id,
            {"name": t.created_by.full_name or t.created_by.username or "Xodim", "projects": set(), "count": 0},
        )
        entry["count"] += 1
        if t.project:
            entry["projects"].add(t.project.name)

    return [
        {"telegram_id": tid, "name": v["name"], "projects": sorted(v["projects"]), "count": v["count"]}
        for tid, v in by_user.items()
    ]


def _format_pending_warning(pending: list[dict]) -> str:
    lines = ["⚠️ Hali tasdiqlanmagan (bugungi hisobotga kirmagan):"]
    for p in pending:
        projects = ", ".join(h(name) for name in p["projects"]) if p["projects"] else "-"
        lines.append(f"• {h(p['name'])} ({projects}): {p['count']} ta yozuv")
    return "\n".join(lines)


async def _sleep_until(hour: int, minute: int) -> datetime:
    now = datetime.now(_TASHKENT)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    await asyncio.sleep((target - now).total_seconds())
    return target


async def run_daftar_reminder(bot: Bot) -> None:
    """Runs forever, nudging (in a private message) any employee who still
    has unconfirmed Daftar entries for today, shortly before the nightly
    digest fires - so they have a chance to confirm and actually appear in
    that day's group report instead of silently being left out of it."""
    if not settings.report_recipient_id:
        return

    while True:
        target = await _sleep_until(_REMINDER_HOUR, _REMINDER_MINUTE)
        try:
            pending = await _pending_users_for_date(target.date())
            for p in pending:
                try:
                    await bot.send_message(
                        chat_id=p["telegram_id"],
                        text=(
                            f"⏰ Eslatma: bugungi Daftaringizda {p['count']} ta tasdiqlanmagan yozuv bor. "
                            "Soat 20:00'da kunlik hisobot tuzilganda tasdiqlanmagan yozuvlar unga "
                            "kirmaydi - iltimos 📒 Daftar orqali ko'rib, tasdiqlab qo'ying."
                        ),
                    )
                except Exception:
                    logger.exception("Failed to send Daftar reminder to %s", p["telegram_id"])
        except Exception:
            logger.exception("Failed to run Daftar reminder job")


async def run_daily_ceo_digest(bot: Bot) -> None:
    """Runs forever, sending a report to REPORT_RECIPIENT_ID (a personal
    chat or a group) every day at 20:00 Tashkent time, covering that day's
    confirmed transactions across all employees/projects - replaces the old
    behavior of pinging the recipient separately every time an employee
    confirmed. Sends one message per project, a final summary message, and
    (if anyone still has unconfirmed entries for the day) a warning listing
    who's missing so the recipient knows the report may be incomplete."""
    if not settings.report_recipient_id:
        return

    while True:
        target = await _sleep_until(_DIGEST_HOUR, 0)
        try:
            recipient_id = int(settings.report_recipient_id)
            rows = await _confirmed_rows_for_date(target.date())
            for report_text in format_project_report_messages(rows) if rows else []:
                await bot.send_message(chat_id=recipient_id, text=report_text)

            pending = await _pending_users_for_date(target.date())
            if pending:
                await bot.send_message(chat_id=recipient_id, text=_format_pending_warning(pending))
        except Exception:
            logger.exception("Failed to send nightly CEO digest")

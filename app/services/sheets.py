"""Sync confirmed transactions to the user's existing Google Sheet.

Uses a Google Apps Script Web App bound to the target spreadsheet as the
write endpoint (see docs/google_sheets_webapp.gs), so the bot only needs a
plain HTTPS POST - no Google Cloud service-account credentials to manage.
"""

import logging

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


async def append_transaction_row(row: dict) -> None:
    """Best-effort append; failures are logged but never raised to callers."""
    if not settings.sheets_webhook_url:
        return

    payload = {"secret": settings.sheets_webhook_secret, **row}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.sheets_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.warning("Sheets webhook returned %s: %s", resp.status, text)
    except Exception:
        logger.exception("append_transaction_row failed")

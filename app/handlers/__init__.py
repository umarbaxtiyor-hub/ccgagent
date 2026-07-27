import logging
import traceback

from aiogram import Router
from aiogram.types import ErrorEvent

from app.handlers.bank_import import router as bank_import_router
from app.handlers.day_review import router as day_review_router
from app.handlers.group_qa import router as group_qa_router
from app.handlers.projects import router as projects_router
from app.handlers.receipt import router as receipt_router
from app.handlers.reports import router as reports_router
from app.handlers.start import router as start_router
from app.handlers.text_entry import router as text_entry_router
from app.handlers.voice import router as voice_router

logger = logging.getLogger(__name__)

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(reports_router)
main_router.include_router(projects_router)
main_router.include_router(day_review_router)
main_router.include_router(bank_import_router)
main_router.include_router(receipt_router)
main_router.include_router(voice_router)
main_router.include_router(group_qa_router)
# text_entry must be included last: it catches plain text messages that no other handler matched
main_router.include_router(text_entry_router)


@main_router.errors()
async def handle_unhandled_error(event: ErrorEvent) -> None:
    """Last-resort safety net: any exception a handler doesn't catch itself
    used to leave the user with total silence - no ack, no error message,
    indistinguishable from the bot being down. This guarantees a reply."""
    logger.exception("Unhandled error while processing update", exc_info=event.exception)

    chat_message = event.update.message or event.update.edited_message
    if event.update.callback_query is not None:
        chat_message = event.update.callback_query.message

    if chat_message is not None:
        try:
            # Temporary diagnostic detail (this is an internal ops bot, no
            # secrets in a bare exception message) so failures can be
            # screenshotted and fixed without needing to dig through
            # Railway's log dashboard for every new bug.
            tb_line = traceback.format_exception(event.exception)[-1].strip()
            await chat_message.answer(
                "Kechirasiz, kutilmagan ichki xatolik yuz berdi. Iltimos, qayta urinib ko'ring.\n"
                f"(texnik xato: {tb_line[:300]})"
            )
        except Exception:
            logger.exception("Failed to notify user about unhandled error")

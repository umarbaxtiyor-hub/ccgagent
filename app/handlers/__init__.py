from aiogram import Router

from app.handlers.bank_import import router as bank_import_router
from app.handlers.day_review import router as day_review_router
from app.handlers.group_qa import router as group_qa_router
from app.handlers.projects import router as projects_router
from app.handlers.receipt import router as receipt_router
from app.handlers.reports import router as reports_router
from app.handlers.start import router as start_router
from app.handlers.text_entry import router as text_entry_router
from app.handlers.voice import router as voice_router

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

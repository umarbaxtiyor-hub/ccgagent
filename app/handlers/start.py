import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.access import AllowedUser
from app.config import settings
from app.db import async_session
from app.handlers.keyboards import new_user_assign_keyboard
from app.services.categories import seed_categories
from app.services.projects import list_projects
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)

BOT_PERSONA_NAME = "Zarina"

HELP_TEXT = (
    "Nima qila olaman:\n"
    "- Erkin matn yozing (masalan: <i>\"Sement uchun 500000 so'm to'ladim\"</i>) - men summani, "
    "kategoriyani va turini o'zim aniqlayman.\n"
    "- Chek yoki kvitansiya rasmini yuboring - undan ma'lumotni o'zim o'qib olaman.\n"
    "- Ovozli xabar yuboring - men uni matnga o'girib, xuddi yozma xabar kabi tahlil qilaman.\n"
    "- Bank ko'chirmasi faylini (.xlsx yoki .csv) yuboring - barcha tranzaksiyalarni avtomatik "
    "kategoriyalarga bo'lib qo'shaman.\n"
    "- /loyiha - qaysi loyiha (obyekt) uchun ishlayotganingizni ko'rish.\n"
    "- /report - kunlik/haftalik/oylik/boshidan hisobotni Excel faylda olish.\n"
    "- /mening_id - o'zingizning Telegram ID'ingizni bilib olish.\n\n"
    "Har bir xabaringizni darhol qabul qilib, kun davomida bir joyga yig'ib boraman - alohida "
    "tasdiqlashingiz shart emas. Kun oxirida /kun_yakuni buyrug'i bilan kiritilgan hammasini ko'rib "
    "chiqasiz: kerak bo'lsa kategoriyasini o'zgartirasiz yoki o'chirasiz, so'ng \"Barchasini "
    "tasdiqlash\" tugmasi bilan yakunlaysiz - shundagina hisobotga tushadi va Google Sheetga yuboriladi.\n\n"
    "Loyihangizni administrator biriktiradi. Agar hali biriktirilmagan bo'lsa, /mening_id orqali "
    "ID'ingizni olib, administratorga yuboring."
)


@router.message(Command("mening_id"))
async def cmd_my_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


@router.message(Command("start"), AllowedUser())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        await seed_categories(session)
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )

        needs_assignment = (
            not user.current_project_id and message.from_user.id not in settings.admin_user_id_set
        )
        if needs_assignment:
            projects = await list_projects(session)

    await message.answer(
        f"Salom, {message.from_user.full_name}! Men {BOT_PERSONA_NAME}man, sizning hisobot "
        "asistentingizman."
    )

    if not needs_assignment:
        return

    admins = settings.admin_user_id_set
    if not admins:
        return

    username_part = f"@{message.from_user.username}" if message.from_user.username else "username yo'q"
    notice = (
        f"🆕 Yangi foydalanuvchi botni ishga tushirdi:\n"
        f"{message.from_user.full_name} ({username_part})\n"
        f"ID: <code>{message.from_user.id}</code>\n\n"
        "Mavjud loyihalardan birini tanlang, yoki yangi loyiha yaratish uchun yozing:\n"
        f"/loyiha_biriktir {message.from_user.id} &lt;loyiha nomi&gt;"
    )
    markup = new_user_assign_keyboard(message.from_user.id, projects) if projects else None
    for admin_id in admins:
        try:
            await message.bot.send_message(chat_id=admin_id, text=notice, reply_markup=markup)
        except Exception:
            logger.exception("Failed to notify admin %s about new user %s", admin_id, message.from_user.id)


@router.message(Command("help"), AllowedUser())
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("start"))
@router.message(Command("help"))
async def cmd_start_denied(message: Message) -> None:
    await message.answer("Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q.")

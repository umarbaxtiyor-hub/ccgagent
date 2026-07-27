import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.access import AllowedUser
from app.config import settings
from app.db import async_session
from app.handlers.keyboards import daftar_reply_keyboard, new_user_assign_keyboard
from app.services.categories import seed_categories
from app.services.projects import list_projects
from app.services.transactions import count_unconfirmed
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
    "tasdiqlashingiz shart emas. Pastdagi \"📒 Daftar\" tugmasini (yoki /daftar buyrug'ini) bosib "
    "kiritilgan hammasini istalgan vaqtda ko'rib chiqasiz: kerak bo'lsa kategoriyasini o'zgartirasiz "
    "yoki o'chirasiz, so'ng \"Hammasini tasdiqlash\" tugmasi bilan yakunlaysiz - shundagina hisobotga "
    "tushadi va Google Sheetga yuboriladi.\n\n"
    "Loyihangizni administrator biriktiradi. Agar hali biriktirilmagan bo'lsa, /mening_id orqali "
    "ID'ingizni olib, administratorga yuboring."
)


@router.message(Command("mening_id"))
async def cmd_my_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


@router.message(Command("guruh_id"))
async def cmd_group_id(message: Message) -> None:
    """Run inside a group so the admin can grab its chat ID for
    REPORT_RECIPIENT_ID - group chat IDs are negative numbers, distinct
    from a personal Telegram user ID."""
    if message.chat.type == "private":
        await message.answer(
            "Bu buyruq guruh ichida ishlaydi - botni guruhga qo'shib, shu yerda /guruh_id deb yozing."
        )
        return
    await message.answer(f"Shu guruhning chat ID'si: <code>{message.chat.id}</code>")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    is_admin = message.from_user.id in settings.admin_user_id_set

    async with async_session() as session:
        await seed_categories(session)
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        is_approved = is_admin or user.is_approved
        needs_assignment = is_approved and not user.current_project_id and not is_admin
        if needs_assignment:
            projects = await list_projects(session)
        count = await count_unconfirmed(session, user.id) if is_approved else 0

    if not is_approved:
        await message.answer(
            "Xush kelibsiz! So'rovingiz administratorga yuborildi - tasdiqlangach botdan "
            "to'liq foydalanishingiz mumkin bo'ladi."
        )
        await _notify_admins_new_user(message, awaiting_approval=True)
        return

    await message.answer(
        f"Salom, {message.from_user.full_name}! Men {BOT_PERSONA_NAME}man, sizning hisobot "
        "asistentingizman.",
        reply_markup=daftar_reply_keyboard(count),
    )

    if needs_assignment:
        await _notify_admins_new_user(message, awaiting_approval=False, projects=projects)


async def _notify_admins_new_user(
    message: Message, awaiting_approval: bool, projects: list | None = None
) -> None:
    admins = settings.admin_user_id_set
    if not admins:
        return

    username_part = f"@{message.from_user.username}" if message.from_user.username else "username yo'q"
    intro = (
        "🆕 Yangi foydalanuvchi botga ruxsat so'rayapti:"
        if awaiting_approval
        else "🆕 Yangi foydalanuvchi botni ishga tushirdi:"
    )
    notice = (
        f"{intro}\n"
        f"{message.from_user.full_name} ({username_part})\n"
        f"ID: <code>{message.from_user.id}</code>\n\n"
        "Mavjud loyihalardan birini tanlang (bu ham ruxsat beradi, ham loyihaga biriktiradi), "
        "yoki loyihasiz ruxsat berish uchun pastdagi tugmani bosing:\n"
        f"/loyiha_biriktir {message.from_user.id} &lt;loyiha nomi&gt;"
    )
    markup = new_user_assign_keyboard(message.from_user.id, projects or [])
    for admin_id in admins:
        try:
            await message.bot.send_message(chat_id=admin_id, text=notice, reply_markup=markup)
        except Exception:
            logger.exception("Failed to notify admin %s about new user %s", admin_id, message.from_user.id)


@router.message(Command("help"), AllowedUser())
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("help"))
async def cmd_help_denied(message: Message) -> None:
    await message.answer("Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q.")

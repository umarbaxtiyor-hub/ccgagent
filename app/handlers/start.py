from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.access import AllowedUser
from app.db import async_session
from app.services.categories import seed_categories
from app.services.users import get_or_create_user

router = Router()

WELCOME_TEXT = (
    "Assalomu alaykum! Men qurilish kompaniyasi uchun xarajat/daromad hisobchi botman.\n\n"
    "Nima qila olaman:\n"
    "- Erkin matn yozing (masalan: <i>\"Sement uchun 500000 so'm to'ladim\"</i>) - men summani, "
    "kategoriyani va turini o'zim aniqlayman.\n"
    "- Chek yoki kvitansiya rasmini yuboring - undan ma'lumotni o'zim o'qib olaman.\n"
    "- Ovozli xabar yuboring - men uni matnga o'girib, xuddi yozma xabar kabi tahlil qilaman.\n"
    "- Bank ko'chirmasi faylini (.xlsx yoki .csv) yuboring - barcha tranzaksiyalarni avtomatik "
    "kategoriyalarga bo'lib qo'shaman.\n"
    "- /loyiha - qaysi loyiha (obyekt) uchun yozayotganingizni tanlash yoki almashtirish.\n"
    "- /loyiha_yarat &lt;nomi&gt; - yangi loyiha qo'shish.\n"
    "- /report - kunlik/haftalik/oylik hisobotni Excel faylda olish.\n\n"
    "Har bir yozuvni saqlashdan oldin tasdiqlashingizni so'rayman."
)


@router.message(Command("start"), AllowedUser())
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        await seed_categories(session)
        await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"), AllowedUser())
async def cmd_help(message: Message) -> None:
    await message.answer(WELCOME_TEXT)


@router.message(Command("start"))
@router.message(Command("help"))
async def cmd_start_denied(message: Message) -> None:
    await message.answer("Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q.")

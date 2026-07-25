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
    "- /report - kunlik/haftalik/oylik hisobotni Excel faylda olish.\n"
    "- /mening_id - o'zingizning Telegram ID'ingizni bilib olish.\n\n"
    "Har bir xabaringizni darhol qabul qilib, kun davomida bir joyga yig'ib boraman - alohida "
    "tasdiqlashingiz shart emas. Kun oxirida /kun_yakuni buyrug'i bilan kiritilgan hammasini ko'rib "
    "chiqasiz: kerak bo'lsa kategoriyasini o'zgartirasiz yoki o'chirasiz, so'ng \"Barchasini "
    "tasdiqlash\" tugmasi bilan yakunlaysiz - shundagina hisobotga tushadi va Google Sheetga yuboriladi."
)


@router.message(Command("mening_id"))
async def cmd_my_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


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

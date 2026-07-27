import logging
from html import escape as h

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.access import AdminUser, AllowedUser
from app.config import settings
from app.db import async_session
from app.handlers.keyboards import project_list_keyboard
from app.services.projects import create_project, list_projects, set_user_current_project
from app.services.users import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("loyiha"), AllowedUser())
async def cmd_loyiha(message: Message) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )

    if message.from_user.id not in settings.admin_user_id_set:
        if user.current_project:
            await message.answer(
                f"Sizning joriy loyihangiz: <b>{h(user.current_project.name)}</b>. O'zgartirish kerak "
                "bo'lsa, administratorga murojaat qiling."
            )
        else:
            await message.answer(
                "Sizga hali loyiha biriktirilmagan. /mening_id buyrug'i orqali o'z ID'ingizni oling va "
                "administratorga yuboring."
            )
        return

    async with async_session() as session:
        projects = await list_projects(session)
    if not projects:
        await message.answer(
            "Hali birorta loyiha qo'shilmagan. /loyiha_yarat &lt;nomi&gt; buyrug'i bilan qo'shing."
        )
        return
    await message.answer("Loyihani tanlang:", reply_markup=project_list_keyboard(projects))


@router.message(Command("loyiha_yarat"), AllowedUser(), AdminUser())
async def cmd_loyiha_yarat(message: Message) -> None:
    name = message.text.replace("/loyiha_yarat", "", 1).strip()
    if not name:
        await message.answer("Iltimos, loyiha nomini ham yozing: /loyiha_yarat Obyekt-2")
        return

    async with async_session() as session:
        project = await create_project(session, name)
        user = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
        )
        await set_user_current_project(session, user.id, project.id)

    await message.answer(f"✅ \"{h(project.name)}\" loyihasi qo'shildi va joriy loyiha sifatida tanlandi.")


@router.message(Command("loyiha_biriktir"), AllowedUser(), AdminUser())
async def cmd_loyiha_biriktir(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer(
            "Foydalanish: /loyiha_biriktir &lt;telegram_id&gt; &lt;loyiha nomi&gt;\n"
            "Masalan: /loyiha_biriktir 123456789 LOT 8\n\n"
            "Xodim o'z Telegram ID'sini /mening_id buyrug'i orqali bilib, sizga yuborishi kerak."
        )
        return

    employee_id = int(parts[1])
    project_name = parts[2].strip()

    async with async_session() as session:
        project = await create_project(session, project_name)
        employee = await get_or_create_user(session, telegram_id=employee_id, full_name="", username="")
        employee.is_approved = True
        await set_user_current_project(session, employee.id, project.id)

    await message.answer(f"✅ Xodim (ID: {employee_id}) \"{h(project.name)}\" loyihasiga biriktirildi.")

    try:
        await message.bot.send_message(
            chat_id=employee_id,
            text=(
                f"📌 Sizga <b>{h(project.name)}</b> loyihasi biriktirildi. Endi yuboradigan barcha "
                "xabarlaringiz shu loyihaga tegishli bo'ladi."
            ),
        )
    except Exception:
        logger.exception("Failed to notify employee %s about project assignment", employee_id)


@router.callback_query(F.data.startswith("newuser_assign:"))
async def assign_new_user(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_user_id_set:
        await callback.answer("Bu amal faqat administrator uchun.", show_alert=True)
        return

    _, employee_id_str, project_id_str = callback.data.split(":", 2)
    employee_id = int(employee_id_str)
    project_id = int(project_id_str)

    async with async_session() as session:
        employee = await get_or_create_user(session, telegram_id=employee_id, full_name="", username="")
        employee.is_approved = True
        await set_user_current_project(session, employee.id, project_id)
        projects = await list_projects(session)
        project = next((p for p in projects if p.id == project_id), None)

    project_name = h(project.name) if project else str(project_id)
    await callback.message.edit_text(
        f"✅ Xodim (ID: {employee_id}) \"{project_name}\" loyihasiga biriktirildi.", reply_markup=None
    )
    await callback.answer("Biriktirildi")

    try:
        await callback.bot.send_message(
            chat_id=employee_id,
            text=(
                f"✅ Sizga botdan foydalanish uchun ruxsat berildi va <b>{project_name}</b> loyihasi "
                "biriktirildi. Endi yuboradigan barcha xabarlaringiz shu loyihaga tegishli bo'ladi."
            ),
        )
    except Exception:
        logger.exception("Failed to notify employee %s about project assignment", employee_id)


@router.callback_query(F.data.startswith("newuser_approve:"))
async def approve_new_user(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_user_id_set:
        await callback.answer("Bu amal faqat administrator uchun.", show_alert=True)
        return

    employee_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        employee = await get_or_create_user(session, telegram_id=employee_id, full_name="", username="")
        employee.is_approved = True
        await session.commit()

    await callback.message.edit_text(f"✅ Xodim (ID: {employee_id}) uchun ruxsat berildi.", reply_markup=None)
    await callback.answer("Ruxsat berildi")

    try:
        await callback.bot.send_message(
            chat_id=employee_id,
            text=(
                "✅ Sizga botdan foydalanish uchun ruxsat berildi! /start buyrug'ini qayta yuboring. "
                "Loyihangiz hali biriktirilmagan bo'lsa, administrator tez orada biriktiradi."
            ),
        )
    except Exception:
        logger.exception("Failed to notify employee %s about approval", employee_id)


@router.callback_query(F.data.startswith("proj_select:"))
async def select_project(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_user_id_set:
        await callback.answer("Bu amal faqat administrator uchun.", show_alert=True)
        return

    project_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name,
            username=callback.from_user.username or "",
        )
        await set_user_current_project(session, user.id, project_id)
        projects = await list_projects(session)
        project = next((p for p in projects if p.id == project_id), None)

    project_name = h(project.name) if project else str(project_id)
    await callback.message.edit_text(
        f"✅ Joriy loyiha: <b>{project_name}</b>. Endi shu loyiha uchun yozishingiz mumkin.",
        reply_markup=None,
    )
    await callback.answer("Tanlandi")

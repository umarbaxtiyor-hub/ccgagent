from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.access import AllowedUser
from app.db import async_session
from app.handlers.keyboards import project_list_keyboard
from app.services.projects import create_project, list_projects, set_user_current_project
from app.services.users import get_or_create_user

router = Router()


@router.message(Command("loyiha"), AllowedUser())
async def cmd_loyiha(message: Message) -> None:
    async with async_session() as session:
        projects = await list_projects(session)
    if not projects:
        await message.answer(
            "Hali birorta loyiha qo'shilmagan. /loyiha_yarat <nomi> buyrug'i bilan qo'shing."
        )
        return
    await message.answer("Loyihani tanlang:", reply_markup=project_list_keyboard(projects))


@router.message(Command("loyiha_yarat"), AllowedUser())
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

    await message.answer(f"✅ \"{project.name}\" loyihasi qo'shildi va joriy loyiha sifatida tanlandi.")


@router.callback_query(F.data.startswith("proj_select:"))
async def select_project(callback: CallbackQuery) -> None:
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

    project_name = project.name if project else project_id
    await callback.message.edit_text(
        f"✅ Joriy loyiha: <b>{project_name}</b>. Endi shu loyiha uchun yozishingiz mumkin.",
        reply_markup=None,
    )
    await callback.answer("Tanlandi")

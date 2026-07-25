from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User


async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id).options(selectinload(User.current_project))
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username or "")
        session.add(user)
        await session.commit()
        await session.refresh(user, attribute_names=["current_project"])
        return user

    # Backfill name/username for rows an admin pre-created (e.g. via
    # /loyiha_biriktir) before the employee ever messaged the bot.
    changed = False
    if not user.full_name and full_name:
        user.full_name = full_name
        changed = True
    if not user.username and username:
        user.username = username
        changed = True
    if changed:
        await session.commit()
    return user

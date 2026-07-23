from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, full_name=full_name, username=username or "")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

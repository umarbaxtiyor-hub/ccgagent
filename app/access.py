from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy import select

from app.config import settings
from app.db import async_session
from app.models import User


class AllowedUser(Filter):
    """Admins are always allowed. Otherwise: an explicit ALLOWED_USER_IDS
    env var (legacy, optional) still grants access if set, and beyond that
    a user needs is_approved=True in the DB - set via an admin tapping
    "approve" on the new-user notification (see projects.py), so granting
    access no longer requires editing Railway env vars and redeploying."""

    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        telegram_id = message.from_user.id

        if telegram_id in settings.admin_user_id_set:
            return True

        allowed = settings.allowed_user_id_set
        if allowed and telegram_id in allowed:
            return True

        async with async_session() as session:
            result = await session.execute(select(User.is_approved).where(User.telegram_id == telegram_id))
            return bool(result.scalar_one_or_none())


class AdminUser(Filter):
    async def __call__(self, message: Message) -> bool:
        admins = settings.admin_user_id_set
        return message.from_user is not None and message.from_user.id in admins

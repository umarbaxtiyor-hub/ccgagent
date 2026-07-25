from aiogram.filters import Filter
from aiogram.types import Message

from app.config import settings


class AllowedUser(Filter):
    async def __call__(self, message: Message) -> bool:
        allowed = settings.allowed_user_id_set
        if not allowed:
            return True
        return message.from_user is not None and message.from_user.id in allowed


class AdminUser(Filter):
    async def __call__(self, message: Message) -> bool:
        admins = settings.admin_user_id_set
        return message.from_user is not None and message.from_user.id in admins

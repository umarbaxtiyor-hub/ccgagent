from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction


async def count_unconfirmed(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.created_by_id == user_id, Transaction.confirmed.is_(False))
    )
    return result.scalar_one()

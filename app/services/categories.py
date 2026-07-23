from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, TransactionType

DEFAULT_EXPENSE_CATEGORIES = [
    "Qurilish materiallari",
    "Ish haqi",
    "Transport",
    "Jihoz va asboblar",
    "Ijara",
    "Kommunal to'lovlar",
    "Soliq va yig'imlar",
    "Boshqa xarajat",
]

DEFAULT_INCOME_CATEGORIES = [
    "Mijoz to'lovi",
    "Kredit / investitsiya",
    "Boshqa daromad",
]


async def seed_categories(session: AsyncSession) -> None:
    existing = (await session.execute(select(Category.name))).scalars().all()
    existing_set = set(existing)

    for name in DEFAULT_EXPENSE_CATEGORIES:
        if name not in existing_set:
            session.add(Category(name=name, type=TransactionType.expense))

    for name in DEFAULT_INCOME_CATEGORIES:
        if name not in existing_set:
            session.add(Category(name=name, type=TransactionType.income))

    await session.commit()


async def category_names(session: AsyncSession, type_: TransactionType) -> list[str]:
    rows = (
        await session.execute(select(Category.name).where(Category.type == type_))
    ).scalars().all()
    return list(rows)


async def get_or_create_category(session: AsyncSession, name: str, type_: TransactionType) -> Category:
    result = await session.execute(select(Category).where(Category.name == name))
    category = result.scalar_one_or_none()
    if category is None:
        category = Category(name=name, type=type_)
        session.add(category)
        await session.flush()
    return category

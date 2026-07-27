from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Project, Transaction, TransactionType


async def _totals_by_project(session: AsyncSession, since: date | None) -> dict[str, dict[str, float]]:
    stmt = (
        select(Project.name, Transaction.type, func.sum(Transaction.amount))
        .select_from(Transaction)
        .join(Project, Transaction.project_id == Project.id, isouter=True)
        .where(Transaction.confirmed.is_(True))
    )
    if since is not None:
        stmt = stmt.where(Transaction.occurred_on >= since)
    stmt = stmt.group_by(Project.name, Transaction.type)

    result = await session.execute(stmt)
    data: dict[str, dict[str, float]] = {}
    for name, ttype, total in result.all():
        data.setdefault(name or "-", {})[ttype.value] = float(total or 0)
    return data


def _format_project_totals(data: dict[str, dict[str, float]]) -> str:
    if not data:
        return "  (ma'lumot yo'q)"
    lines = []
    for name, vals in data.items():
        income = vals.get("income", 0.0)
        expense = vals.get("expense", 0.0)
        lines.append(f"  {name}: kirim={income:,.0f}, chiqim={expense:,.0f}, balans={income - expense:,.0f}")
    return "\n".join(lines)


async def build_data_summary(session: AsyncSession) -> str:
    """Precomputes exact aggregates (today / this month / all-time, per
    project, plus a category breakdown) as plain text for the group Q&A
    feature - the AI is instructed to answer using ONLY these numbers
    rather than inventing its own, since this is financial data."""
    today = date.today()
    month_start = today.replace(day=1)

    today_totals = await _totals_by_project(session, today)
    month_totals = await _totals_by_project(session, month_start)
    all_totals = await _totals_by_project(session, None)

    cat_stmt = (
        select(Category.name, func.sum(Transaction.amount))
        .join(Category, Transaction.category_id == Category.id)
        .where(Transaction.confirmed.is_(True), Transaction.type == TransactionType.expense)
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    cat_result = await session.execute(cat_stmt)
    cat_rows = cat_result.all()
    cat_text = (
        "\n".join(f"  {name}: {float(total):,.0f} so'm" for name, total in cat_rows)
        if cat_rows
        else "  (ma'lumot yo'q)"
    )

    return (
        f"Bugungi sana: {today.isoformat()}\n\n"
        f"BUGUNGI ma'lumotlar (loyiha bo'yicha, faqat tasdiqlangan yozuvlar):\n"
        f"{_format_project_totals(today_totals)}\n\n"
        f"SHU OYLIK ma'lumotlar (loyiha bo'yicha, {month_start.isoformat()} dan hozirgacha):\n"
        f"{_format_project_totals(month_totals)}\n\n"
        f"BOSHIDAN HOZIRGACHA JAMI (loyiha bo'yicha):\n"
        f"{_format_project_totals(all_totals)}\n\n"
        f"Kategoriya bo'yicha jami chiqimlar (boshidan hozirgacha):\n{cat_text}"
    )

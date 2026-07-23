from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.name))
    return list(result.scalars().all())


async def create_project(session: AsyncSession, name: str) -> Project:
    result = await session.execute(select(Project).where(Project.name == name))
    project = result.scalar_one_or_none()
    if project is None:
        project = Project(name=name)
        session.add(project)
        await session.commit()
        await session.refresh(project)
    return project


async def set_user_current_project(session: AsyncSession, user_id: int, project_id: int) -> None:
    user = await session.get(User, user_id)
    user.current_project_id = project_id
    await session.commit()

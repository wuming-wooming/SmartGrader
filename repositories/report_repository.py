"""
Report 数据访问层

创建者：童天宇
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.report import Report


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Report:
        report = Report(**kwargs)
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_by_task(self, task_id: int) -> Report | None:
        stmt = select(Report).where(Report.task_id == task_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.user_id == user_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

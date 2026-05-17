"""
QuestionResult 数据访问层

创建者：童天宇
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.question_result import QuestionResult


class QuestionResultRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> QuestionResult:
        qr = QuestionResult(**kwargs)
        self.session.add(qr)
        await self.session.flush()
        return qr

    async def get_by_task(self, task_id: int) -> list[QuestionResult]:
        stmt = (
            select(QuestionResult)
            .where(QuestionResult.task_id == task_id)
            .order_by(QuestionResult.page_num, QuestionResult.question_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

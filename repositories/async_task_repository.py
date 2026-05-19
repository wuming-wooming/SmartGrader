"""
AsyncTask（Celery 追踪）数据访问层

创建者：童天宇
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.async_task import AsyncTask


class AsyncTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, assignment_task_id: int, celery_task_id: str) -> AsyncTask:
        at = AsyncTask(
            assignment_task_id=assignment_task_id,
            celery_task_id=celery_task_id,
            status=0,
        )
        self.session.add(at)
        await self.session.commit()
        await self.session.refresh(at)
        return at

    async def update_status(
        self,
        assignment_task_id: int,
        status: int,
        error_detail: str | None = None,
        retry_count: int | None = None,
    ) -> None:
        values: dict = {"status": status}
        if error_detail:
            values["error_detail"] = error_detail
        if retry_count is not None:
            values["retry_count"] = retry_count
        stmt = (
            update(AsyncTask)
            .where(AsyncTask.assignment_task_id == assignment_task_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_by_celery_id(self, celery_task_id: str) -> AsyncTask | None:
        stmt = select(AsyncTask).where(AsyncTask.celery_task_id == celery_task_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

"""
AssignmentTask 数据访问层

创建者：童天宇
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.assignment_task import AssignmentTask


class AssignmentTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        task_type: int,
        original_file: str,
        total_pages: int = 1,
        processed_file: str | None = None,
    ) -> AssignmentTask:
        task = AssignmentTask(
            user_id=user_id,
            task_type=task_type,
            original_file=original_file,
            total_pages=total_pages,
            processed_file=processed_file,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: int) -> AssignmentTask | None:
        return await self.session.get(AssignmentTask, task_id)

    async def get_by_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[AssignmentTask]:
        stmt = (
            select(AssignmentTask)
            .where(AssignmentTask.user_id == user_id)
            .order_by(AssignmentTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self, task_id: int, status: int, error_msg: str | None = None
    ) -> None:
        values: dict = {"task_status": status}
        if error_msg:
            values["error_msg"] = error_msg
        stmt = (
            update(AssignmentTask)
            .where(AssignmentTask.id == task_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.commit()

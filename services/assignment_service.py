"""
作业任务服务模块
处理与作业任务 (AssignmentTask) 相关的数据库操作

日期： 2026/5/15

创建者：周康哲
"""

from sqlalchemy.ext.asyncio import AsyncSession
from models.assignment_task import AssignmentTask


# 在数据库中创建一条新的作业任务记录
async def create_assignment_task(
    db: AsyncSession,
    user_id: int,
    original_file: str,
    processed_file: str = None,
    task_type: int = 1,
    total_pages: int = 1,
) -> AssignmentTask:
    """
    创建数据库中的作业任务记录

    :param db: 数据库异步会话
    :param user_id: 关联的用户ID
    :param original_file: 原始图片的相对路径或URL
    :param processed_file: 清洗后图片的相对路径或URL
    :param task_type: 任务类型：1=单题，2=整页，3=多页 (默认1)
    :param total_pages: 作业总页数 (默认1)
    :return: 创建成功的 AssignmentTask 实例
    """
    new_task = AssignmentTask(
        user_id=user_id,
        task_type=task_type,
        total_pages=total_pages,
        original_file=original_file,
        processed_file=processed_file,
        task_status=0,
    )

    # 添加到事务并提交
    db.add(new_task)
    await db.commit()

    # 刷新以获取数据库生成的自增 ID
    await db.refresh(new_task)

    return new_task

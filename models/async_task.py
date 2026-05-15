"""
异步任务日志实体类

日期： 2026/5/14

创建者：童天宇
"""
from __future__ import annotations  # 延迟解析注解，3.7+支持

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger, VARCHAR, TEXT, INT, SMALLINT, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)

from core.database import Base

# 仅类型检查时导入，运行时不执行，避免循环依赖
if TYPE_CHECKING:
    from models import AssignmentTask


class AsyncTask(Base):
    """异步任务日志实体类"""
    __tablename__ = "async_tasks"
    __table_args__ = (
        UniqueConstraint("assignment_task_id", name="uk_async_task_assignment"),
        UniqueConstraint("celery_task_id", name="uk_async_task_celery"),
        # 索引：任务状态、创建时间
        Index("idx_async_status", "status"),
        Index("idx_async_created_at", "created_at"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="异步日志ID"
    )
    assignment_task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assignment_tasks.id", ondelete="CASCADE"), comment="关联作业任务ID"
    )
    celery_task_id: Mapped[str] = mapped_column(
        VARCHAR(100), nullable=False, comment="Celery任务ID"
    )
    status: Mapped[int] = mapped_column(
        SMALLINT, default=0, comment="任务状态：0=待执行，1=执行中，2=成功，3=失败"
    )
    retry_count: Mapped[int] = mapped_column(
        INT, default=0, comment="重试次数"
    )
    error_detail: Mapped[str | None] = mapped_column(
        TEXT, comment="错误详情"
    )

    # 关联关系
    assignment_task: Mapped["AssignmentTask"] = relationship(back_populates="async_task")

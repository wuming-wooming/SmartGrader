"""
作业任务实体类

日期： 2026/5/14

创建者：童天宇
"""
from __future__ import annotations  # 延迟解析注解，3.7+支持

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger, VARCHAR, DATETIME, TEXT, INT, SMALLINT, ForeignKey, Index
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)

from core.database import Base

# 仅类型检查时导入，运行时不执行，避免循环依赖
if TYPE_CHECKING:
    from models import (
        User, QuestionResult, Report, AsyncTask
    )


class AssignmentTask(Base):
    """作业任务实体类"""
    __tablename__ = "assignment_tasks"
    __table_args__ = (
        # 联合索引：用户ID+任务状态（高并发下快速筛选用户的任务）
        Index("idx_task_user_status", "user_id", "task_status"),
        # 普通索引：创建时间、任务类型
        Index("idx_task_created_at", "created_at"),
        Index("idx_task_type", "task_type"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="任务ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), comment="关联用户ID"
    )
    task_type: Mapped[int] = mapped_column(
        SMALLINT, comment="任务类型：1=单题，2=整页，3=多页"
    )
    total_pages: Mapped[int] = mapped_column(
        INT, default=1, comment="作业总页数"
    )
    original_file: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="原始图片OSS根路径"
    )
    processed_file: Mapped[str | None] = mapped_column(
        VARCHAR(255), comment="预处理后图片OSS根路径"
    )
    task_status: Mapped[int] = mapped_column(
        SMALLINT, default=0, comment="任务状态：0=待处理，1=处理中，2=完成，3=失败"
    )
    error_msg: Mapped[str | None] = mapped_column(
        TEXT, comment="失败错误信息"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DATETIME, comment="任务完成时间"
    )

    # 关联关系
    user: Mapped["User"] = relationship(back_populates="assignment_tasks")
    question_results: Mapped[list["QuestionResult"]] = relationship(
        back_populates="assignment_task", cascade="all, delete-orphan"
    )
    report: Mapped["Report"] = relationship(
        back_populates="assignment_task", cascade="all, delete-orphan"
    )
    async_task: Mapped["AsyncTask"] = relationship(
        back_populates="assignment_task", cascade="all, delete-orphan"
    )

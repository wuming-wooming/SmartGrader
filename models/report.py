"""
批阅任务最终报告表

日期： 2026/5/14

创建者：童天宇
"""
from __future__ import annotations  # 延迟解析注解，3.7+支持

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger, TEXT, INT, SMALLINT, JSON, ForeignKey, Index, UniqueConstraint, DECIMAL
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)

from core.database import Base

# 仅类型检查时导入，运行时不执行，避免循环依赖
if TYPE_CHECKING:
    from models import AssignmentTask


class Report(Base):
    """
    批阅任务最终报告表
    """
    __tablename__ = "reports"
    __table_args__ = (
        # 唯一索引：保证一个任务只有一份报告
        UniqueConstraint("task_id", name="uk_report_task_id"),
        # 高并发查询索引
        Index("idx_report_user_id", "user_id"),
        Index("idx_report_task_type", "task_type"),
        Index("idx_report_task_status", "task_status"),
        Index("idx_report_created_at", "created_at"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="报告ID"
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assignment_tasks.id", ondelete="CASCADE"), comment="关联批阅任务ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, comment="关联用户ID"
    )
    total_score: Mapped[float] = mapped_column(
        DECIMAL(7, 2), nullable=False, comment="最终得分"
    )
    max_total_score: Mapped[float] = mapped_column(
        DECIMAL(7, 2), nullable=False, comment="满分"
    )
    correct_count: Mapped[int] = mapped_column(
        INT, nullable=False, comment="做对题目数"
    )
    total_questions: Mapped[int] = mapped_column(
        INT, nullable=False, comment="总题目数"
    )
    subject_list: Mapped[dict | list | None] = mapped_column(
        JSON, comment="学科标签列表，如 ['数学','英语']"
    )
    page_count: Mapped[int] = mapped_column(
        INT, default=1, comment="批阅总页数"
    )
    task_type: Mapped[int] = mapped_column(
        SMALLINT, comment="任务类型：1=单题，2=整页，3=多页"
    )
    task_status: Mapped[int] = mapped_column(
        SMALLINT, comment="最终状态：2=完成，3=失败"
    )
    summary: Mapped[str | None] = mapped_column(
        TEXT, comment="批阅总评"
    )
    suggestion: Mapped[str | None] = mapped_column(
        TEXT, comment="改进建议"
    )

    # 关联关系：一份报告对应一个任务
    assignment_task: Mapped["AssignmentTask"] = relationship(
        back_populates="report"
    )

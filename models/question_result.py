"""
题目批改结果实体类

日期： 2026/5/14

创建者：童天宇
"""
from __future__ import annotations  # 延迟解析注解，3.7+支持

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger, VARCHAR, TEXT, INT, SMALLINT, JSON, ForeignKey, Index, DECIMAL
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)

from core.database import Base

# 仅类型检查时导入，运行时不执行，避免循环依赖
if TYPE_CHECKING:
    from models import AssignmentTask


class QuestionResult(Base):
    """题目批改结果实体类"""
    __tablename__ = "question_results"
    __table_args__ = (
        # 联合索引：任务ID+页码（批量查询某任务某页的题目）
        Index("idx_question_task_page", "task_id", "page_num"),
        # 普通索引：学科、是否正确
        Index("idx_question_subject", "subject"),
        Index("idx_question_is_correct", "is_correct"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="题目结果ID"
    )
    task_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assignment_tasks.id", ondelete="CASCADE"), comment="关联任务ID"
    )
    page_num: Mapped[int] = mapped_column(
        INT, default=1, nullable=False, comment="题目所在页码"
    )
    question_index: Mapped[int] = mapped_column(
        INT, nullable=False, comment="题目在页面中的序号"
    )
    subject: Mapped[str] = mapped_column(
        VARCHAR(20), nullable=False, comment="学科标签：数学/语文/英语等"
    )
    question_text: Mapped[str | None] = mapped_column(
        TEXT, comment="OCR识别的题目文本"
    )
    question_image: Mapped[str | None] = mapped_column(
        VARCHAR(255), comment="题目裁剪图片OSS地址"
    )
    is_correct: Mapped[int] = mapped_column(
        SMALLINT, comment="是否正确：1=对，0=错"
    )
    score: Mapped[float] = mapped_column(
        DECIMAL(7, 2), nullable=False, comment="题目得分"
    )
    full_score: Mapped[float] = mapped_column(
        DECIMAL(7, 2), nullable=False, comment="题目满分"
    )
    error_reason: Mapped[str | None] = mapped_column(
        TEXT, comment="错误原因"
    )
    correct_answer: Mapped[str | None] = mapped_column(
        TEXT, comment="正确答案提示"
    )
    comment: Mapped[str | None] = mapped_column(
        TEXT, comment="详细批注"
    )
    coordinate: Mapped[dict | None] = mapped_column(
        JSON, comment="题目坐标：{x1,y1,x2,y2}"
    )

    # 关联关系
    assignment_task: Mapped["AssignmentTask"] = relationship(back_populates="question_results")

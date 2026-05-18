"""
用户实体类

日期： 2026/5/13

创建者：童天宇
"""
from __future__ import annotations  # 延迟解析注解，3.7+支持

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger, VARCHAR, SMALLINT, Index, UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)

from core.database import Base

# 仅类型检查时导入，运行时不执行，避免循环依赖
if TYPE_CHECKING:
    from models import AssignmentTask


class User(Base):
    """用户实体类"""
    __tablename__ = "users"
    __table_args__ = (
        # 唯一索引：用户名、邮箱
        UniqueConstraint("username", name="uk_username"),
        UniqueConstraint("email", name="uk_email"),
        # 普通索引：创建时间、是否激活
        Index("idx_user_created_at", "created_at"),
        Index("idx_user_is_active", "is_active"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}  # 高并发推荐InnoDB
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="用户ID"
    )
    username: Mapped[str] = mapped_column(
        VARCHAR(50), nullable=False, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        VARCHAR(100), nullable=False, comment="用户邮箱"
    )
    hashed_password: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, comment="加密密码"
    )
    avatar: Mapped[str | None] = mapped_column(
        VARCHAR(255), comment="用户头像OSS地址"
    )
    is_active: Mapped[int] = mapped_column(
        SMALLINT, default=1, comment="是否激活：1=激活，0=禁用"
    )

    # 关联关系：一个用户对应多个作业任务
    assignment_tasks: Mapped[list["AssignmentTask"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

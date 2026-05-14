"""
数据库引擎模块

日期： 2026/5/13

创建者：童天宇
"""

from datetime import datetime

from sqlalchemy import func, DATETIME
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.config import (
    DATABASE_URL,
    DATABASE_POOL_SIZE,
    DATABASE_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_TIMEOUT
)

# 创建异步引擎 —— 配置连接池参数应对高并发
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 生产环境设为 False，避免日志冗余
    pool_size=DATABASE_POOL_SIZE,  # 连接池常驻连接数（根据并发量调整）
    max_overflow=DATABASE_MAX_OVERFLOW,  # 允许临时创建的额外连接数
    pool_timeout=DATABASE_POOL_RECYCLE,  # 获取连接的超时时间（秒）
    pool_recycle=DATABASE_POOL_TIMEOUT,  # 连接回收时间（秒），避免 MySQL 8小时超时
    pool_pre_ping=True,  # 每次使用前检查连接是否存活
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # 提交后不使对象过期，提升性能
)


# 模型基类（所有实体类继承此类）
class Base(DeclarativeBase):
    """数据库模型基类，封装通用字段"""
    # 通用字段：创建时间、更新时间
    created_at: Mapped[datetime] = mapped_column(
        DATETIME, default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME, default=func.now(), onupdate=func.now(), comment="更新时间"
    )


# 依赖注入：获取数据库会话（每个请求独立会话）
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# 初始化数据库表（应用启动时调用）
# noinspection PyUnusedImports
async def init_db():
    import models  # 别删，用来显示导入所有实体类，避免表未被创建
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# 导出供外部使用
__all__ = ["engine", "AsyncSessionLocal", "get_db", "init_db", "Base"]

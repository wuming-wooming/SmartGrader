"""
用户服务模块

日期： 2026/5/13

创建者：童天宇
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.password_util import PasswordUtil
from models.user import User


# 根据用户名查找用户
async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()


# 根据邮箱查找用户
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()


# 创建新用户
async def create_user(db: AsyncSession, username: str, email: str, password: str) -> User:
    hashed_pw = PasswordUtil.hash(password)
    user = User(username=username, email=email, hashed_password=hashed_pw)
    db.add(user)
    await db.commit()  # 提交事务
    await db.refresh(user)  # 刷新获取自增 id
    return user


# 验证用户登录
async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not PasswordUtil.verify(password, user.hashed_password):
        return None
    return user

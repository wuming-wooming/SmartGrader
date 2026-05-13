"""
用户管理接口路由模块

日期： 2026/5/13

创建者：童天宇
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import create_access_token, get_current_user
from core.database import get_db
from schemas.user_schemas import *
from services.user_service import create_user, authenticate_user, get_user_by_username, get_user_by_email

# 创建路由对象
router = APIRouter(
    prefix="/users",
    tags=["用户管理"]
)

class UserRouter:
    """
    用户管理接口路由类
    """

    @router.post("/register", response_model=TokenResponse, summary="用户注册")
    async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
        """
        用户注册接口函数
        :param user: 用户注册信息
        :param db: 数据库会话
        :return: 登录令牌
        """
        # 检查用户名是否已存在
        if await get_user_by_username(db, user.username):
            raise HTTPException(status_code=400, detail="用户名已被注册")
        # 检查邮箱是否已存在
        if await get_user_by_email(db, user.email):
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        # 创建新用户
        new_user = await create_user(db, user.username, user.email, user.password)
        # 签发JWT令牌
        token = create_access_token({"sub": str(new_user.id), "username": new_user.username})
        return TokenResponse(access_token=token)

    @router.post("/login", response_model=TokenResponse, summary="用户登录")
    async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
        """
        用户登录接口函数
        :param user: 用户登录信息
        :param db: 数据库会话
        :return: 登录令牌
        """
        # 验证用户
        current_user = await authenticate_user(db, user.username, user.password)
        if not current_user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        # 签发JWT令牌
        token = create_access_token({"sub": str(current_user.id), "username": current_user.username})
        return TokenResponse(access_token=token)

    @router.get("/protected", summary="需验证的接口示例")
    async def protected(current_user: dict = Depends(get_current_user)):
        return {"message": f"Hello {current_user['username']}, 您已通过JWT验证！"}

# 实例化路由类，让路由控制器生效
UserRouter()
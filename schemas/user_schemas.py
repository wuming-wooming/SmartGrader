"""
用户数据传递模型（用户视图）

日期： 2026/5/13

创建者：童天宇
"""

from pydantic import BaseModel, EmailStr


# 注册请求体结构
class UserRegister(BaseModel):
    username: str
    email: EmailStr  # 自动校验邮箱格式
    password: str


# 登录请求体结构
class UserLogin(BaseModel):
    username: str
    password: str


# Token 响应结构
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

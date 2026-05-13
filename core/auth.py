"""
认证核心逻辑

日期： 2026/5/13

创建者：童天宇
"""

from datetime import datetime, timedelta

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# 密码加密上下文
pwd_context = CryptContext(
    schemes=[
        "argon2",
        "pbkdf2_sha256"
    ],
    default="argon2",
    deprecated="auto"
)

# HTTP Bearer 安全方案（用于 Swagger 自动添加授权按钮）
security = HTTPBearer()

# ---------- JWT 操作 ----------
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# 验证 JWT 并返回当前用户信息（依赖注入核心）
async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    该函数会从请求头 Authorization: Bearer <token> 中提取 token，
    验证有效性并返回用户基本信息。如果失效则抛出 401 错误。
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")
        if user_id is None or username is None:
            raise HTTPException(status_code=401, detail="无效凭证")
        return {"id": int(user_id), "username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="无效凭证")

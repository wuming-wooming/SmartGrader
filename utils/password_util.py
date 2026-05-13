"""
密码处理工具模块

日期： 2026/5/13

创建者：童天宇
"""

from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(
    schemes=[
        "argon2",
        "pbkdf2_sha256"
    ],
    default="argon2",
    deprecated="auto"
)

class PasswordUtil:
    """
    密码处理工具类
    """

    @staticmethod
    def hash(password: str) -> str:
        """
        同步加密
        :param password: 密码字串
        :return: 加密后的字串
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """
        同步验证
        :param plain_password: 明文密码
        :param hashed_password: 密文密码
        :return: 验证结果
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    async def hash_async(password: str) -> str:
        """
        异步加密
        :param password: 密码字串
        :return: 加密后的字串
        """
        return await pwd_context.hash(password)

    @staticmethod
    async def verify_async(plain_password: str, hashed_password: str) -> bool:
        """
        异步验证
        :param plain_password: 明文密码
        :param hashed_password: 密文密码
        :return: 验证结果
        """
        return await pwd_context.verify(plain_password, hashed_password)
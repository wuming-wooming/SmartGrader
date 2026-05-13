"""
全局配置

日期： 2026/5/13

创建者：童天宇
"""

# ---------- 加密配置 ----------
SECRET_KEY = "685c2ff0fcc89c41602e7cfae3972accd775242ff8f5e3c06cfa53bf0f167e8e"  # 密钥（随机字符串）
ALGORITHM = "HS256"  # 加密算法
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # JWT登录令牌有效期：30分钟

# ---------- 数据库配置 ----------
# MySQL 连接字符串格式：mysql+aiomysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
# ATTENTION: 注意改成自己的数据库密码
DATABASE_URL = "mysql+aiomysql://root:tty0726@localhost:3306/smart_grader?charset=utf8mb4"
DATABASE_POOL_SIZE = 20  # 连接池常驻连接数（根据并发量调整）
DATABASE_MAX_OVERFLOW = 30  # 允许临时创建的额外连接数
DATABASE_POOL_TIMEOUT = 30  # 获取连接的超时时间（秒）
DATABASE_POOL_RECYCLE = 3600  # 连接回收时间（秒），避免 MySQL 8小时超时

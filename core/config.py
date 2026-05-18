"""
全局配置

日期：2026/5/13
创建者：童天宇
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- 加密配置 ----------
SECRET_KEY = os.getenv("SECRET_KEY", "685c2ff0fcc89c41602e7cfae3972accd775242ff8f5e3c06cfa53bf0f167e8e")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# ---------- 数据库配置 ----------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:tty0726@localhost:3306/smart_grader?charset=utf8mb4"
)
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "20"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "30"))
DATABASE_POOL_TIMEOUT = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
DATABASE_POOL_RECYCLE = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))

# ---------- Celery 配置 ----------
SYNC_DATABASE_URL = os.getenv(
    "SYNC_DATABASE_URL",
    "mysql+pymysql://root:tty0726@localhost:3306/smart_grader?charset=utf8mb4"
)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ---------- 任务重试配置 ----------
TASK_MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))
TASK_RETRY_BACKOFF = int(os.getenv("TASK_RETRY_BACKOFF", "10"))
TASK_RETRY_BACKOFF_MAX = int(os.getenv("TASK_RETRY_BACKOFF_MAX", "600"))

# ---------- LLM 配置 ----------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
LLM_CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "5"))

# ---------- OSS 配置 ----------
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "")
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")

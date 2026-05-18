"""
Celery 实例初始化与配置

日期： 2026/5/15

创建者：周康哲
"""

from celery import Celery
from core.config import REDIS_URL

#创建 Celery 实例
# broker: 消息代理（接收 FastAPI 发来的任务并存起来排队）
# backend: 结果存储 （记录任务执行成功还是失败）
celery_app = Celery(
    "smart_grader_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['services.image_service', 'services.ocr_service'] # 告诉 Celery 去哪里找任务函数
)

# Celery 运行配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_concurrency=4,
)

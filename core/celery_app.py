"""
Celery 实例初始化与配置

日期： 2026/5/15

创建者：周康哲
"""

from celery import Celery

from core.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

#创建 Celery 实例
# broker: 消息代理（接收 FastAPI 发来的任务并存起来排队）
# backend: 结果存储 （记录任务执行成功还是失败）
celery_app = Celery(
    "smart_grader",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks.grading_tasks", "tasks.image_tasks", "tasks.ocr_tasks", "tasks.baidu_homework_tasks"],
)

# Celery 运行配置
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    worker_concurrency=4
)

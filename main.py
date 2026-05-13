"""
FastAPI主模块文件

日期： 2026/5/13

创建者：PyCharm自动生成
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.database import init_db, engine


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_db()
    yield
    # 关闭时执行
    await engine.dispose()


# 创建 FastAPI 实例
app = FastAPI(
    title="Smart Grader",
    description="基于大模型的中小学作业批改系统",
    version="0.0.1",
    lifespan=lifespan
)

# 注册路由
from routers import user_router

app.include_router(user_router.router)

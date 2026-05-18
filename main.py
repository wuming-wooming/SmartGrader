"""
FastAPI主模块文件

日期： 2026/5/13

创建者：PyCharm自动生成
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.database import init_db, engine


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_db()
    print("数据库初始化完成")
    yield
    # 关闭时执行
    await engine.dispose()


# 创建 FastAPI 实例
app = FastAPI(
    title="Smart Grader",
    description="基于大模型的中小学作业批改系统",
    version="0.0.1",
    lifespan=lifespan,
)

# 注册路由
from routers import user_router, image_router

app.include_router(user_router.router)
app.include_router(image_router.router)

# 挂载静态文件目录，让前端可以直接通过 URL 访问图片
import os

os.makedirs("data/raw_images", exist_ok=True)
os.makedirs("data/processed_images", exist_ok=True)
app.mount("/data", StaticFiles(directory="data"), name="data")

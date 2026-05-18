"""
图像处理接口路由模块
处理图片上传，创建数据库记录，并将图片清洗任务提交给 Celery 后台执行。

日期： 2026/5/18

创建者：周康哲
"""

import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.database import get_db
from schemas.image_schemas import ImageProcessResponse
from services.assignment_service import create_assignment_task
from services.image_service import process_homework_image_task

# 创建路由对象
router = APIRouter(prefix="/images", tags=["图像处理与作业提交"])

# 确保图片存储位置
RAW_DIR = "data/raw_images"
PROCESSED_DIR = "data/processed_images"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


class ImageRouter:
    """
    图像处理接口路由类

    核心流程：
        1. 接收前端图片并保存到本地。
        2. 在数据库 assignment_tasks 表中创建一条初始任务记录（状态：0待处理）。
        3. 将清洗任务提交给 Celery 后台执行。
        4. 立刻向前端返回任务ID，不阻塞等待清洗完成。
    """

    @router.post(
        "/upload_and_clean",
        response_model=ImageProcessResponse,
        summary="上传并清洗图片",
    )
    async def upload_and_clean_image(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        """
        上传并清洗图片接口函数
        :param file: 图片文件
        :param current_user: 当前用户信息
        :param db: 数据库会话
        :return: 图片处理响应
        """

        # 校验文件类型
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="文件类型必须为图片")

        # 生成唯一文件名
        file_ext = os.path.splitext(file.filename)[1]
        if not file_ext:
            file_ext = ".jpg"
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"

        # 物理路径 (给 python 读写使用)
        raw_path = os.path.join(RAW_DIR, unique_filename)
        processed_path = os.path.join(PROCESSED_DIR, f"cleaned_{unique_filename}")

        # url 路径 (给前端访问使用)
        raw_url = f"{RAW_DIR}/{unique_filename}"
        processed_url = f"{PROCESSED_DIR}/{f'cleaned_{unique_filename}'}"

        # 保存原始图片到本地
        try:
            with open(raw_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"保存原始图片到本地失败: {str(e)}"
            )

        # 存入数据库：创建初始任务 (此时清洗还没开始，不填写 processed_file)
        try:
            new_task = await create_assignment_task(
                db=db,
                user_id=current_user["id"],
                original_file=raw_url,
                processed_file=None,
                task_type=2,  # 默认整页
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建数据库任务失败: {str(e)}")

        # 异步提交给 Celery 进行后台处理
        # 注意：使用 .delay() 方法，把参数打包发给 Redis，函数会瞬间执行完毕，不等待处理结果
        process_homework_image_task.delay(
            assignment_task_id=new_task.id,
            input_path=raw_path,
            output_path=processed_path,
            processed_url=processed_url,
        )

        # 立刻给前端返回响应
        return ImageProcessResponse(
            task_id=new_task.id,
            message="图片已成功上传，后台正在排队清洗中...",
            raw_image_url=raw_url,
            task_status=0,  # 待处理
        )


# 实例化路由让其生效
ImageRouter()

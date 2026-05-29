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
from models.question_result import QuestionResult
from schemas.image_schemas import ImageProcessResponse, CutImageItem, CutImageListResponse
from services.assignment_service import create_assignment_task
from tasks.image_tasks import process_homework_image_task

# 创建路由对象
router = APIRouter(prefix="/images", tags=["图像处理与作业提交"])

# 确保图片存储位置
RAW_DIR = "data/raw_images"
PROCESSED_DIR = "data/processed_images"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


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
    上传图片, 保存到本地, 创建 AssignmentTask 记录, 提交 Celery 后台清洗任务.
    核心流程: 接收图片 → 入库(status=0) → 提交Celery → 立即返回task_id
    """

    # 校验文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
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
        task_status=0,
    )


@router.get(
    "/{task_id}/cuts",
    response_model=CutImageListResponse,
    summary="获取切题后的图片列表",
)
async def get_cut_images(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    根据任务ID返回切题后的每道题图片及元数据，便于前端逐题展示。
    
    返回字段包括：
    - question_id: 题目数据库主键
    - question_index: 题目在页内序号
    - page_num: 页码
    - subject: 学科标签
    - question_text: OCR 识别文本
    - image_url: 裁剪图片的可访问 URL（已通过 /data 静态挂载）
    - coordinate: 题目在原图上的坐标包围盒
    """
    from sqlalchemy import select

    stmt = (
        select(QuestionResult)
        .where(QuestionResult.task_id == task_id)
        .order_by(QuestionResult.page_num, QuestionResult.question_index)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 尚无切题数据，请确认 OCR 已完成",
        )

    cuts = [
        CutImageItem(
            question_id=q.id,
            question_index=q.question_index,
            page_num=q.page_num,
            subject=q.subject,
            question_text=q.question_text,
            image_url=q.question_image,
            coordinate=q.coordinate,
        )
        for q in rows
    ]

    return CutImageListResponse(
        task_id=task_id,
        total=len(cuts),
        cuts=cuts,
    )

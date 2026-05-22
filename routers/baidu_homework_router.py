"""
百度云智能作业批改 API 端点
独立于现有 OCR 路线，失败时自动回退

日期： 2026/5/22
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.database import get_db
from models.async_task import AsyncTask
from repositories.assignment_task_repository import AssignmentTaskRepository
from repositories.async_task_repository import AsyncTaskRepository
from repositories.question_result_repository import QuestionResultRepository
from repositories.report_repository import ReportRepository
from schemas.grading_schemas import (
    QuestionResultItem,
    ReportItem,
    TaskResultResponse,
    TaskStatusResponse,
)
from tasks.baidu_homework_tasks import baidu_homework_grading_task

router = APIRouter(prefix="/baidu-homework", tags=["百度云作业批改"])

STATUS_LABELS = {0: "pending", 1: "processing", 2: "completed", 3: "failed"}
RAW_DIR = "data/raw_images"


@router.post("/submit", summary="提交图片到百度云智能作业批改")
async def submit_baidu_homework(
    file: UploadFile = File(...),
    only_split: bool = Form(False),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传图片，提交到百度云智能作业批改 API"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    user_id = current_user["id"]

    # 保存图片
    os.makedirs(RAW_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(RAW_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 创建 AssignmentTask
    task_repo = AssignmentTaskRepository(db)
    assignment_task = await task_repo.create(
        user_id=user_id,
        task_type=2,  # full page
        original_file=filepath,
        total_pages=1,
        processed_file=filepath,
    )

    # 分发 Celery 任务
    celery_task = baidu_homework_grading_task.delay(
        assignment_task.id, filepath, only_split
    )

    async_repo = AsyncTaskRepository(db)
    await async_repo.create(assignment_task.id, celery_task.id)

    return {
        "assignment_task_id": assignment_task.id,
        "celery_task_id": celery_task.id,
        "status": "submitted",
        "only_split": only_split,
    }


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="查询百度作业批改任务状态")
async def get_baidu_homework_status(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_repo = AssignmentTaskRepository(db)
    task = await task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    stmt = select(AsyncTask).where(AsyncTask.assignment_task_id == task_id)
    result = await db.execute(stmt)
    async_task = result.scalars().first()

    return TaskStatusResponse(
        assignment_task_id=task.id,
        task_status=task.task_status,
        task_status_label=STATUS_LABELS.get(task.task_status, "unknown"),
        celery_task_id=async_task.celery_task_id if async_task else "",
        async_status=async_task.status if async_task else 0,
        retry_count=async_task.retry_count if async_task else 0,
        error_msg=task.error_msg,
        created_at=task.created_at,
        finished_at=task.finished_at,
    )


@router.get("/result/{task_id}", response_model=TaskResultResponse, summary="获取百度作业批改结果")
async def get_baidu_homework_result(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_repo = AssignmentTaskRepository(db)
    task = await task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    if task.task_status != 2:
        raise HTTPException(status_code=400, detail="任务尚未完成，请稍后查询")

    qr_repo = QuestionResultRepository(db)
    questions = await qr_repo.get_by_task(task_id)

    report_repo = ReportRepository(db)
    report = await report_repo.get_by_task(task_id)

    return TaskResultResponse(
        assignment_task_id=task.id,
        task_status=task.task_status,
        task_type=task.task_type,
        questions=[
            QuestionResultItem(
                question_index=q.question_index,
                page_num=q.page_num,
                subject=q.subject,
                question_text=q.question_text,
                is_correct=q.is_correct,
                score=float(q.score),
                full_score=float(q.full_score),
                error_reason=q.error_reason,
                correct_answer=q.correct_answer,
                comment=q.comment,
            )
            for q in questions
        ],
        report=ReportItem(
            total_score=float(report.total_score),
            max_total_score=float(report.max_total_score),
            correct_count=report.correct_count,
            total_questions=report.total_questions,
            subject_list=report.subject_list or [],
            page_count=report.page_count,
            summary=report.summary,
            suggestion=report.suggestion,
        )
        if report
        else None,
    )

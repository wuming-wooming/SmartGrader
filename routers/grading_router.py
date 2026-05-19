"""
批阅任务 API 端点

创建者：童天宇
"""
from fastapi import APIRouter, Depends, HTTPException
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
    SubmitTaskRequest,
    SubmitTaskResponse,
    TaskListItem,
    TaskListResponse,
    TaskResultResponse,
    TaskStatusResponse,
)
from services.ocr_service import OCRService
from tasks.grading_tasks import submit_for_grading

router = APIRouter(prefix="/grading", tags=["作业批改"])

STATUS_LABELS = {0: "pending", 1: "processing", 2: "completed", 3: "failed"}


@router.post("/submit", response_model=SubmitTaskResponse, summary="提交批改任务")
async def submit_task(
    req: SubmitTaskRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user["id"]

    try:
        validated_questions = OCRService.validate_ocr_data(
            [q.model_dump() for q in req.questions]
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    task_repo = AssignmentTaskRepository(db)
    assignment_task = await task_repo.create(
        user_id=user_id,
        task_type=req.task_type,
        original_file=req.original_file,
        total_pages=req.total_pages,
        processed_file=req.processed_file,
    )

    # 提交 Celery 并在 db 中创建追踪记录
    celery_task = submit_for_grading.delay(assignment_task.id, validated_questions)

    async_repo = AsyncTaskRepository(db)
    await async_repo.create(assignment_task.id, celery_task.id)

    return SubmitTaskResponse(
        assignment_task_id=assignment_task.id,
        celery_task_id=celery_task.id,
    )


@router.get("/status/{task_id}", response_model=TaskStatusResponse, summary="查询任务状态")
async def get_task_status(
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


@router.get("/result/{task_id}", response_model=TaskResultResponse, summary="获取批改结果")
async def get_task_result(
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


@router.get("/tasks", response_model=TaskListResponse, summary="获取任务列表")
async def list_tasks(
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_repo = AssignmentTaskRepository(db)
    tasks = await task_repo.get_by_user(current_user["id"], limit=limit, offset=offset)

    items = []
    for t in tasks:
        qr_repo = QuestionResultRepository(db)
        qrs = await qr_repo.get_by_task(t.id)
        items.append(
            TaskListItem(
                assignment_task_id=t.id,
                task_type=t.task_type,
                total_pages=t.total_pages,
                task_status=t.task_status,
                task_status_label=STATUS_LABELS.get(t.task_status, "unknown"),
                created_at=t.created_at,
                finished_at=t.finished_at,
                total_questions=len(qrs),
            )
        )

    return TaskListResponse(tasks=items, total=len(items), limit=limit, offset=offset)

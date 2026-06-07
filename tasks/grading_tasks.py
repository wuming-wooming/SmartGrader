"""
Celery 异步批改任务模块

使用 Chord 模式：N 题并行评分 → 汇聚后自动生成报告
流程: submit_for_grading → chord([grade_single_question × N], generate_report)

创建者：童天宇
"""
import asyncio
import logging
from datetime import datetime

from celery import chord
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.orm import sessionmaker

from core.celery_app import celery_app
from core.config import (
    TASK_MAX_RETRIES,
    TASK_RETRY_BACKOFF,
    TASK_RETRY_BACKOFF_MAX, )
from repositories.question_result_repository import QuestionResultRepositorySync
from services.grading_service import GradingService

# Windows 上强制使用 SelectorEventLoop（ProactorEventLoop 与 aiomysql 不兼容）
# if sys.platform == 'win32':
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# 注意：Celery solo 模式串行执行，每个 asyncio.run() 创建独立事件循环。
# 引擎不能缓存（绑定到创建时的事件循环），因此 _get_session_local() 每次新建引擎。

logger = logging.getLogger(__name__)

# ===========================================================================
# Celery Worker 数据库引擎（每次调用新建，避免不同事件循环冲突）
# ===========================================================================


def _get_session_local() -> sessionmaker:
    """每次调用新建引擎（asyncio.run() 每次创建新事件循环，引擎不能跨循环复用）"""
    # engine = create_async_engine(
    #     # DATABASE_URL,
    #     SYNC_DATABASE_URL,
    #     pool_size=DATABASE_POOL_SIZE,
    #     max_overflow=DATABASE_MAX_OVERFLOW,
    #     pool_timeout=DATABASE_POOL_TIMEOUT,
    #     pool_recycle=DATABASE_POOL_RECYCLE,
    #     pool_pre_ping=True,
    # )
    # return async_sessionmaker(engine, class_=Session, expire_on_commit=False)

    from core.database import SyncSessionLocal
    return SyncSessionLocal


def _update_task_status(
    task_id: int, status: int, error_msg: str | None = None, finished_at: datetime | None = None
) -> None:
    from models.assignment_task import AssignmentTask

    SessionLocal = _get_session_local()
    with SessionLocal() as session:
        task = session.get(AssignmentTask, task_id)
        if task:
            task.task_status = status
            if error_msg:
                task.error_msg = error_msg
            if finished_at:
                task.finished_at = finished_at
            session.commit()


def _update_async_status(
    assignment_task_id: int, status: int, error_detail: str | None = None
) -> None:
    from sqlalchemy import select

    from models.async_task import AsyncTask

    SessionLocal = _get_session_local()
    with SessionLocal() as session:
        stmt = select(AsyncTask).where(
            AsyncTask.assignment_task_id == assignment_task_id
        )
        result = session.execute(stmt)
        at = result.scalars().first()
        if at:
            at.status = status
            if error_detail:
                at.error_detail = error_detail
            session.commit()


# ===========================================================================
# 入口任务
# ===========================================================================
@celery_app.task(
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_BACKOFF,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=TASK_RETRY_BACKOFF_MAX,
)
def submit_for_grading(self, assignment_task_id: int, ocr_data: list[dict]):
    """
    批阅入口任务。
    1. 更新状态 0→1 (processing)
    2. 构建 Chord 并分发
    """
    celery_task_id = self.request.id

    try:
        _update_task_status(assignment_task_id, 1)
        _update_async_status(assignment_task_id, 1)
        _clear_old_question_results(assignment_task_id)
    except Exception as e:
        logger.exception("更新任务状态失败 task_id=%d", assignment_task_id)
        raise

    # chord: [N个并行评分] → 汇聚后触发 generate_report
    chord(
        [
            grade_single_question.s(assignment_task_id, q_data)
            for q_data in ocr_data
        ],
        generate_report.s(assignment_task_id),
    ).apply_async()

    logger.info(
        "批阅 Chord 已分发 task_id=%d celery_id=%s questions=%d",
        assignment_task_id, celery_task_id, len(ocr_data),
    )
    return {"assignment_task_id": assignment_task_id, "status": "dispatched"}

def _clear_old_question_results(assignment_task_id: int):
    SessionLocal = _get_session_local()
    with SessionLocal() as session:
        repo = QuestionResultRepositorySync(session)
        repo.delete_by_task_id(assignment_task_id)
        session.commit()

# ===========================================================================
# 单题评分任务（Chord 内的并行单元）
# ===========================================================================
@celery_app.task(
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_BACKOFF,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=TASK_RETRY_BACKOFF_MAX,
    acks_late=True,
)
def grade_single_question(self, assignment_task_id: int, question_data: dict) -> dict:
    """
    单题 LLM 批阅。
    返回评分 dict，由 chord 汇聚后传入 generate_report。
    """
    try:
        result = asyncio.run(
            _grade_and_persist(assignment_task_id, question_data)
        )
        return result
    except MaxRetriesExceededError:
        raise
    except Exception as e:
        logger.exception(
            "单题评阅异常 task_id=%d q_index=%d", assignment_task_id, question_data.get("question_index")
        )
        raise


async def _grade_and_persist(assignment_task_id: int, question_data: dict) -> dict:
    grading_service = GradingService()
    grading_result = await grading_service.grade_question(question_data)

    SessionLocal = _get_session_local()
    with SessionLocal() as session:
        repo = QuestionResultRepositorySync(session)
        repo.create(
            task_id=assignment_task_id,
            page_num=question_data["page_num"],
            question_index=question_data["question_index"],
            subject=question_data["subject"],
            question_text=question_data.get("question_text"),
            question_image=question_data.get("question_image"),
            is_correct=grading_result["is_correct"],
            score=grading_result["score"],
            full_score=question_data["full_score"],
            error_reason=grading_result.get("error_reason"),
            correct_answer=grading_result.get("correct_answer"),
            comment=grading_result.get("comment"),
            coordinate=question_data.get("coordinate"),
        )
        session.commit()

    return grading_result


# ===========================================================================
# 报告生成任务（Chord 回调）
# ===========================================================================
@celery_app.task(
    bind=True,
    max_retries=TASK_MAX_RETRIES,
    default_retry_delay=TASK_RETRY_BACKOFF,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=TASK_RETRY_BACKOFF_MAX,
)
def generate_report(self, results: list[dict], assignment_task_id: int):
    """
    Chord 回调：所有题目评完后聚合生成报告。
    results 是 grade_single_question 返回值的列表。
    """
    try:
        asyncio.run(_do_generate_report(assignment_task_id))
    except MaxRetriesExceededError:
        _handle_final_failure(assignment_task_id, "报告生成任务重试耗尽")
        raise
    except Exception as e:
        logger.exception("报告生成异常 task_id=%d", assignment_task_id)
        raise

    return {"assignment_task_id": assignment_task_id, "status": "completed"}


async def _do_generate_report(assignment_task_id: int):
    from models.assignment_task import AssignmentTask

    from services.report_service import ReportService

    SessionLocal = _get_session_local()
    with SessionLocal() as session:
        service = ReportService()
        await service.generate_and_save_report(session, assignment_task_id)

        task = session.get(AssignmentTask, assignment_task_id)
        if task:
            task.task_status = 2
            task.finished_at = datetime.utcnow()
            session.commit()

    _update_async_status(assignment_task_id, 2)


# ===========================================================================
# 最终失败处理
# ===========================================================================
def _handle_final_failure(assignment_task_id: int, error_msg: str) -> None:
    """所有重试耗尽后的兜底处理"""
    try:
        _update_task_status(assignment_task_id, 3, error_msg)
        _update_async_status(assignment_task_id, 3, error_msg)
    except Exception:
        logger.exception("兜底失败处理异常 task_id=%d", assignment_task_id)


# 绑定 submit_for_grading 的最终失败回调
def _on_submit_failure(exc, task_id, args, kwargs, einfo):
    aid = args[0] if args else kwargs.get("assignment_task_id", 0)
    _handle_final_failure(aid, f"{type(exc).__name__}: {exc}")


submit_for_grading.on_failure = _on_submit_failure

"""
百度云智能作业批改 Celery 异步任务
流程: 提交 Baidu API → 轮询结果 → 解析入库 → (可选) LLM 复核
失败时自动回退到现有 OCR 引擎路线

日期： 2026/5/22
"""
import logging
import os

from sqlalchemy import select

from core.celery_app import celery_app
from core.config import BAIDU_HOMEWORK_ENABLED, BAIDU_HOMEWORK_LLM_REVIEW
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from models.question_result import QuestionResult

logger = logging.getLogger(__name__)

CUT_DIR = "data/cut_images"


def _sync_update_db_status(assignment_task_id: int, celery_task_id: str,
                           status: int, error: str = None):
    """同步更新作业任务和异步任务状态"""
    with SyncSessionLocal() as db:
        task = db.get(AssignmentTask, assignment_task_id)
        if task:
            task.task_status = status
            if error:
                task.error_msg = error

        stmt = select(AsyncTask).where(AsyncTask.assignment_task_id == assignment_task_id)
        result = db.execute(stmt)
        async_log = result.scalars().first()
        if async_log:
            async_log.status = status
            async_log.celery_task_id = celery_task_id
            if error:
                async_log.error_detail = error
        else:
            db.add(AsyncTask(
                assignment_task_id=assignment_task_id,
                celery_task_id=celery_task_id,
                status=status,
                error_detail=error,
            ))
        db.commit()


def _do_fallback(assignment_task_id: int, image_path: str, celery_id: str, reason: str):
    """回退到现有 OCR 管线"""
    logger.warning("百度作业批改失败，回退到标准 OCR 管线: %s", reason)
    from tasks.ocr_tasks import process_ocr_task
    process_ocr_task.delay(
        assignment_task_id=assignment_task_id,
        processed_image_path=image_path,
        raw_image_path=image_path,
    )


@celery_app.task(bind=True, name="baidu_homework_grading_task")
def baidu_homework_grading_task(self, assignment_task_id: int, image_path: str,
                                only_split: bool = False):
    """
    百度云智能作业批改任务

    :param assignment_task_id: 数据库作业任务ID
    :param image_path: 原始图片物理路径
    :param only_split: True=仅切题不批改, False=端到端批改
    """
    if not BAIDU_HOMEWORK_ENABLED:
        _do_fallback(assignment_task_id, image_path, self.request.id,
                      "BAIDU_HOMEWORK_ENABLED=false")
        return {"status": "fallback", "task_id": assignment_task_id}

    if not os.path.exists(image_path):
        _sync_update_db_status(assignment_task_id, self.request.id, status=3,
                                error=f"图片不存在: {image_path}")
        return {"status": "failed", "task_id": assignment_task_id}

    try:
        from services.baidu_homework_grading import BaiduHomeworkGradingAPI

        with open(image_path, "rb") as f:
            image_data = f.read()

        api = BaiduHomeworkGradingAPI()
        baidu_task_id = api.submit_task(image_data, only_split=only_split)
        raw_result = api.poll_result(baidu_task_id)
        questions = api.parse_grading_result(raw_result, original_image_path=image_path)

        if not questions:
            _do_fallback(assignment_task_id, image_path, self.request.id,
                          "百度 API 返回空题目列表")
            return {"status": "fallback", "task_id": assignment_task_id}

        # 保存切题结果到数据库
        CUT_DIR = "data/cut_images"
        os.makedirs(CUT_DIR, exist_ok=True)
        with SyncSessionLocal() as db:
            from services.ocr_service import _save_question_results, _crop_question_image, CUT_DIR

            # 构造兼容 cut_result 格式
            cut_result = {
                "part_info": [{"part_title": "", "subject_list": questions}],
                "page_id": 1,
            }
            saved_count = _save_question_results(
                db, assignment_task_id, cut_result,
                crop_source_path=image_path,
                ocr_content=None,
            )

            # 回填百度批改结果
            if not only_split:
                _backfill_baidu_grading(db, assignment_task_id, questions)

        _sync_update_db_status(assignment_task_id, self.request.id, status=2)

        # 可选：触发 LLM 复核批阅
        if not only_split and BAIDU_HOMEWORK_LLM_REVIEW:
            _trigger_llm_review(assignment_task_id)
            logger.info("百度批改完成 task_id=%d saved=%d (LLM复核已触发)",
                        assignment_task_id, saved_count)
        else:
            logger.info("百度批改完成 task_id=%d saved=%d", assignment_task_id, saved_count)

        return {"status": "success", "task_id": assignment_task_id, "questions_saved": saved_count}

    except Exception as e:
        logger.exception("百度作业批改异常 task_id=%d", assignment_task_id)
        _do_fallback(assignment_task_id, image_path, self.request.id, str(e))
        return {"status": "fallback", "task_id": assignment_task_id}


def _backfill_baidu_grading(db, assignment_task_id: int, questions: list[dict]):
    """将百度 API 返回的批改结果回填到 QuestionResult 表中"""
    stmt = (
        select(QuestionResult)
        .where(QuestionResult.task_id == assignment_task_id)
        .order_by(QuestionResult.question_index)
    )
    rows = db.execute(stmt).scalars().all()

    for i, q_data in enumerate(questions):
        if i >= len(rows):
            break
        row = rows[i]
        baidu_score = q_data.get("baidu_score", 0)
        baidu_is_correct = q_data.get("baidu_is_correct", 0)
        baidu_comment = q_data.get("baidu_comment", "")
        full_score = q_data.get("full_score", 0)

        if baidu_score or full_score:
            row.score = baidu_score
            row.full_score = full_score if full_score else baidu_score
            row.is_correct = baidu_is_correct
            row.comment = baidu_comment

    db.commit()
    logger.info("百度批改结果已回填 task_id=%d count=%d", assignment_task_id, min(len(rows), len(questions)))


def _trigger_llm_review(assignment_task_id: int):
    """触发 LLM 复核批阅（复用现有 Chord 管线）"""
    from repositories.question_result_repository import QuestionResultRepository
    from schemas.grading_schemas import OCRDataItem

    # 使用独立的 async session 读取题目数据
    import asyncio

    async def _build_and_submit():
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            repo = QuestionResultRepository(session)
            results = await repo.get_by_task(assignment_task_id)

            ocr_data = []
            for q in results:
                ocr_data.append({
                    "page_num": q.page_num,
                    "question_index": q.question_index,
                    "subject": q.subject or "default",
                    "question_text": q.question_text or "",
                    "question_image": q.question_image,
                    "coordinate": q.coordinate,
                    "full_score": float(q.full_score) if q.full_score else 10.0,
                })

        from tasks.grading_tasks import submit_for_grading
        submit_for_grading.delay(assignment_task_id, ocr_data)
        logger.info("LLM 复核批阅已分发 task_id=%d questions=%d",
                    assignment_task_id, len(ocr_data))

    try:
        asyncio.run(_build_and_submit())
    except Exception:
        logger.exception("触发 LLM 复核失败 task_id=%d，请手动提交批阅", assignment_task_id)

"""
百度云智能作业批改 Celery 异步任务
流程: 提交 Baidu API → 轮询结果 → 解析入库 → LLM 复核
失败时自动回退到现有 OCR 引擎路线

日期： 2026/5/22
"""
import logging
import os

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session
from celery import group, chord

from core.celery_app import celery_app
from core.config import BAIDU_HOMEWORK_ENABLED, BAIDU_HOMEWORK_LLM_REVIEW, BAIDU_HOMEWORK_AUTO_REVIEW
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


def _crop_question_image(image_path: str, crop_url: str) -> bool:
    """同步下载单题切图并保存到本地"""
    try:
        ret = requests.get(crop_url)
        ret.raise_for_status()
        with open(image_path, "wb") as f:
            f.write(ret.content)
        return True
    except Exception:
        raise Exception("Crop question image failed")


@celery_app.task(bind=True, name="baidu_download_crop_task")
def _async_download_crop_task(self, question_id: int, crop_url: str,
                              assignment_task_id: int, page_num: int, question_index: int):
    """异步下载单题切图并更新数据库"""
    try:
        os.makedirs(CUT_DIR, exist_ok=True)
        filename = f"{assignment_task_id}_{page_num}_{question_index}.png"
        image_path = os.path.join(CUT_DIR, filename)

        _crop_question_image(image_path, crop_url)

        with SyncSessionLocal() as db:
            q = db.get(QuestionResult, question_id)
            if q:
                q.question_image = image_path
                db.commit()
                logger.info("下载切图成功 question_id=%d path=%s", question_id, image_path)
            else:
                logger.error("未找到题目记录 question_id=%d", question_id)
        return True
    except Exception as e:
        logger.exception("下载切图失败 question_id=%d url=%s", question_id, crop_url)
        raise self.retry(exc=e, max_retries=3, countdown=5)


@celery_app.task(name="baidu_after_all_crops_downloaded")
def _after_all_crops_downloaded(results, assignment_task_id: int, only_split: bool):
    """所有切图下载完成后的回调，触发LLM复核"""
    logger.info("所有切图下载完成，共 %d 个任务，开始触发LLM复核", len(results))
    if not only_split and BAIDU_HOMEWORK_LLM_REVIEW and BAIDU_HOMEWORK_AUTO_REVIEW:
        import asyncio
        trigger_llm_review(assignment_task_id)
    else:
        logger.info("only_split为True或LLM复核未启用，跳过复核")


def _save_baidu_question_result(assignment_task_id: int, db: Session, questions: list[dict]):
    """
    保存百度返回的题目信息到数据库，不下载切图。
    返回 (保存数量, 待下载任务参数列表)
    """
    saved_count = 0
    download_items = []
    for idx, q in enumerate(questions):
        page_num = q.get("page_num", 1)
        new_question = QuestionResult(
            task_id=assignment_task_id,
            page_num=page_num,
            question_index=idx + 1,
            subject=q.get("subject_label", "default"),
            question_text=q.get("text", ""),
            question_image="",  # 空，等待异步下载填充
            coordinate=q.get("coordinate", None),
            is_correct=q.get("baidu_is_correct", 0),
            score=q.get("baidu_score", 0),
            full_score=q.get("baidu_full_score", 0),
            comment=q.get("baidu_comment", ""),
        )
        db.add(new_question)
        db.flush()  # 获取自增ID
        download_items.append({
            "question_id": new_question.id,
            "crop_url": q["crop_url"],
            "page_num": page_num,
            "question_index": idx + 1,
        })
        saved_count += 1
    db.commit()
    return saved_count, download_items


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

# @celery_app.task(bind=True, name="baidu_homework_grading_task")
def trigger_llm_review(assignment_task_id: int):
    """触发 LLM 复核批阅（复用现有 Chord 管线）"""
    from repositories.question_result_repository import QuestionResultRepository
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
                    "is_correct": q.is_correct,
                    "comment": q.comment or "",
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
        # baidu_task_id = "2061734371172862512"  # 测试用
        raw_result = api.poll_result(baidu_task_id)
        questions = api.parse_grading_result(raw_result, original_image_path=image_path)

        if not questions:
            _do_fallback(assignment_task_id, image_path, self.request.id,
                         "百度 API 返回空题目列表")
            return {"status": "fallback", "task_id": assignment_task_id}

        # 保存题目到数据库（不下载切图）
        with SyncSessionLocal() as db:
            saved_count, download_items = _save_baidu_question_result(
                assignment_task_id, db, questions
            )

        _sync_update_db_status(assignment_task_id, self.request.id, status=2)

        # 异步下载所有切图，全部完成后触发 LLM 复核
        if download_items:
            download_group = group(
                _async_download_crop_task.s(
                    item["question_id"], item["crop_url"],
                    assignment_task_id, item["page_num"], item["question_index"]
                ) for item in download_items
            )
            callback = _after_all_crops_downloaded.s(assignment_task_id, only_split)
            chord(download_group)(callback)
            logger.info("已发起异步下载切图任务，共 %d 张", len(download_items))
        else:
            # 没有切图需要下载，直接决定是否触发复核
            if not only_split and BAIDU_HOMEWORK_LLM_REVIEW and BAIDU_HOMEWORK_AUTO_REVIEW:
                trigger_llm_review(assignment_task_id)

        return {"status": "success", "task_id": assignment_task_id, "questions_saved": saved_count}

    except Exception as e:
        logger.exception("百度作业批改异常 task_id=%d", assignment_task_id)
        _do_fallback(assignment_task_id, image_path, self.request.id, str(e))
        return {"status": "fallback", "task_id": assignment_task_id}
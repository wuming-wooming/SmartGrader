"""
Celery 异步 OCR 识别与切题任务模块
读取清洗后图片，执行 OCR 识别 + 结构化切题，结果写入 question_results 表。
同时根据坐标从图片裁剪出题目图片。

创建者：罗東明
"""
import os
import logging

from sqlalchemy import select

from core.celery_app import celery_app
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from services.ocr_engine import get_ocr_engine
from services.ocr_service import _save_question_results

logger = logging.getLogger(__name__)

CUT_DIR = "data/cut_images"


def _sync_update_db_status(
    assignment_task_id: int,
    celery_task_id: str,
    status: int,
    error: str = None,
):
    """
    同步更新数据库中的作业任务状态和异步日志状态

    :param assignment_task_id: 作业主表记录ID
    :param celery_task_id: Celery 分配的任务UUID
    :param status: 状态码 (2=完成, 3=失败)
    :param error: 错误信息
    """
    with SyncSessionLocal() as db:
        assignment_task = db.get(AssignmentTask, assignment_task_id)
        if assignment_task:
            assignment_task.task_status = status
            if error:
                assignment_task.error_msg = error

        stmt = select(AsyncTask).where(AsyncTask.assignment_task_id == assignment_task_id)
        result = db.execute(stmt)
        async_log = result.scalars().first()
        if async_log:
            async_log.status = status
            async_log.celery_task_id = celery_task_id
            if error:
                async_log.error_detail = error
        else:
            new_log = AsyncTask(
                assignment_task_id=assignment_task_id,
                celery_task_id=celery_task_id,
                status=status,
                error_detail=error if error else None,
            )
            db.add(new_log)

        db.commit()


@celery_app.task(bind=True, name="process_ocr_task")
def process_ocr_task(
    self,
    assignment_task_id: int,
    processed_image_path: str = None,
    raw_image_path: str = None,
):
    """
    Celery 后台任务：对图片进行 OCR 识别 + 结构化切题，结果存入 question_results 表
    切题优先使用 RecognizeEduPaperStructed（精细版结构化切题，内置图像增强），
    如果 part_info 为空则回退 RecognizeEduPaperCut（旧版）进行重试
    同时根据坐标从 processed_image 裁剪出题目图片保存到 data/cut_images/

    :param self: Celery任务实例自身 (为了获取 request.id)
    :param assignment_task_id: 数据库中的作业任务ID
    :param processed_image_path: 清洗后图片的物理路径（用于OCR文字识别 + 裁剪源图）
    :param raw_image_path: 原始图片的物理路径（用于结构化切题，Structed 内置图像增强）
    """
    try:
        # 决定用哪张图做OCR识别：优先 processed，其次 raw
        ocr_image_path = processed_image_path if processed_image_path and os.path.exists(processed_image_path) else raw_image_path
        if not ocr_image_path or not os.path.exists(ocr_image_path):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"OCR识别的图片不存在 (processed={processed_image_path}, raw={raw_image_path})",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        # 结构化切题优先用原始图片（Structed 内置图像增强，无需预处理）
        cut_image_path = raw_image_path if raw_image_path and os.path.exists(raw_image_path) else ocr_image_path
        # 裁剪题目图片时优先用原始图片（坐标来自原始图片空间）
        crop_source_path = raw_image_path if raw_image_path and os.path.exists(raw_image_path) else processed_image_path

        # 步骤1：整页试卷识别（用 processed 图片获取 OCR 结果用于展示/验证）
        engine = get_ocr_engine()
        with open(ocr_image_path, "rb") as f:
            image_body = f.read()
        ocr_type = "scan" if ocr_image_path == processed_image_path else "photo"
        ocr_result = engine.page_recognize(image_data=image_body, image_type=ocr_type)
        if not ocr_result or not ocr_result.get("content"):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OCR整页识别返回空结果",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        # 额外对原始图片做 OCR 用于文本拆分（原始图片 OCR 质量通常更好）
        ocr_content_for_split = ocr_result.get("content", "")
        if cut_image_path != ocr_image_path and os.path.exists(cut_image_path):
            try:
                with open(cut_image_path, "rb") as f_raw:
                    raw_body = f_raw.read()
                raw_ocr_type = "photo"
                raw_ocr = engine.page_recognize(image_data=raw_body, image_type=raw_ocr_type)
                if raw_ocr and raw_ocr.get("content"):
                    raw_text = raw_ocr["content"]
                    if len(raw_text) > len(ocr_content_for_split):
                        ocr_content_for_split = raw_text
            except Exception:
                pass

        # 步骤2：结构化切题（引擎内部处理回退逻辑）
        with open(cut_image_path, "rb") as f:
            cut_body = f.read()

        try:
            cut_result = engine.paper_cut(image_data=cut_body, subject="default")
        except Exception as e:
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"所有切题方案均返回空结果: {e}",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        print(f"切题成功：{type(engine).__name__}")

        # 步骤3：将切题结果写入 question_results 表，同时裁剪题目图片
        os.makedirs(CUT_DIR, exist_ok=True)
        with SyncSessionLocal() as db:
            saved_count = _save_question_results(
                db, assignment_task_id, cut_result,
                crop_source_path=crop_source_path,
                ocr_content=ocr_content_for_split,
            )

        _sync_update_db_status(
            assignment_task_id,
            self.request.id,
            status=2,
        )

        return {
            "status": "success",
            "task_id": assignment_task_id,
            "questions_saved": saved_count,
        }

    except Exception as e:
        try:
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"OCR处理发生异常: {str(e)}",
            )
        except Exception as inner_e:
            print(f"更新数据库状态失败: {inner_e}")
        raise e

"""
OCR识别与切题服务模块
提供阿里云整页试卷识别和题目裁剪功能，通过Celery后台任务串联：读取清洗后图片 → OCR识别 → 切题 → 结果入库
同时根据切题坐标从清洗后图片裁剪出题目图片，保存到 data/cut_images/

日期： 2026/5/18

创建者：罗東明
"""
import json
import os
import uuid

import cv2

from alibabacloud_ocr_api20210707.models import (
    RecognizeEduPaperOcrRequest,
    RecognizeEduPaperCutRequest,
)
from sqlalchemy import select

from core.celery_app import celery_app
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from models.question_result import QuestionResult
from utils.aliyun_client import ocr_client

# 裁剪图片保存目录
CUT_DIR = "data/cut_images"


def page_recognize(
    body: bytes,
    image_type: str = "photo",
    subject: str = "default",
    output_oricoord: bool = False,
) -> dict:
    """
    整页试卷识别，调用阿里云 RecognizeEduPaperOcr 接口

    :param body: 图片二进制数据
    :param image_type: 图片类型，photo 或 scan
    :param subject: 学科标签
    :param output_oricoord: 是否输出原图坐标
    :return: 识别结果字典
    """
    request = RecognizeEduPaperOcrRequest(
        image_type=image_type,
        subject=subject,
        output_oricoord=output_oricoord,
    )
    request.body = body
    response = ocr_client.recognize_edu_paper_ocr(request)
    return json.loads(response.body.data)


def paper_cut(
    body: bytes,
    cut_type: str = "question",
    image_type: str = "photo",
    subject: str = "default",
    output_oricoord: bool = False,
) -> dict:
    """
    试卷切题，调用阿里云 RecognizeEduPaperCut 接口

    :param body: 图片二进制数据
    :param cut_type: 裁剪类型，默认 question
    :param image_type: 图片类型，photo 或 scan
    :param subject: 学科标签
    :param output_oricoord: 是否输出原图坐标
    :return: 切题结果字典
    """
    request = RecognizeEduPaperCutRequest(
        cut_type=cut_type,
        image_type=image_type,
        subject=subject,
        output_oricoord=output_oricoord,
    )
    request.body = body
    response = ocr_client.recognize_edu_paper_cut(request)
    return json.loads(response.body.data)


def _crop_question_image(
    image_path: str, coordinate: dict, output_path: str
) -> bool:
    """
    根据坐标从原图中裁剪出题目区域并保存

    :param image_path: 原图物理路径（清洗后的图片）
    :param coordinate: 题目坐标 {"x1", "y1", "x2", "y2"}
    :param output_path: 裁剪后的图片保存路径
    :return: 成功返回 True，失败返回 False
    """
    if not os.path.exists(image_path):
        return False
    img = cv2.imread(image_path)
    if img is None:
        return False

    h, w = img.shape[:2]
    x1 = max(0, int(coordinate.get("x1", 0)))
    y1 = max(0, int(coordinate.get("y1", 0)))
    x2 = min(w, int(coordinate.get("x2", w)))
    y2 = min(h, int(coordinate.get("y2", h)))

    if x2 <= x1 or y2 <= y1:
        return False

    cropped = img[y1:y2, x1:x2]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, cropped)
    return True


def _save_question_results(
    db, task_id: int, cut_result: dict, crop_source_path: str = None
) -> int:
    """
    将切题结果逐题写入 question_results 表
    阿里云 paper_cut 返回结构: page_list → subject_list 每个 subject 即一道题目
    同时根据坐标从 crop_source_path 裁剪出题目图片存入 data/cut_images/

    :param db: 同步数据库会话
    :param task_id: 关联的作业任务ID
    :param cut_result: 阿里云切题接口返回的原始字典
    :param crop_source_path: 用于裁剪的原图物理路径（清洗后图片），为 None 则不裁剪
    :return: 入库的题目数量
    """
    page_list = cut_result.get("page_list", [])
    if not page_list:
        return 0

    saved_count = 0
    for page in page_list:
        page_num = page.get("doc_index", 1)
        subject_list = page.get("subject_list", [])
        for idx, subject in enumerate(subject_list):
            question_text = subject.get("text", "")

            # 坐标信息从 content_list_info 的 pos 数组中取
            coordinate = None
            content_list = subject.get("content_list_info", [])
            if content_list:
                pos_list = content_list[0].get("pos", [])
                if pos_list and len(pos_list) >= 2:
                    # pos 是 [{x, y}, {x, y}, ...] 格式
                    xs = [p.get("x", 0) for p in pos_list]
                    ys = [p.get("y", 0) for p in pos_list]
                    coordinate = {
                        "x1": min(xs) if xs else 0,
                        "y1": min(ys) if ys else 0,
                        "x2": max(xs) if xs else 0,
                        "y2": max(ys) if ys else 0,
                    }

            new_question = QuestionResult(
                task_id=task_id,
                page_num=page_num,
                question_index=idx + 1,
                subject=subject.get("ids", [{}])[0].get("subject", "default") if subject.get("ids") else "default",
                question_text=question_text if question_text else None,
                question_image=None,  # 先占位，裁剪成功后再更新
                coordinate=coordinate,
                is_correct=0,  # 0=待批改，后续LLM处理
                score=0,
                full_score=0,
            )
            db.add(new_question)
            db.flush()  # 刷新以获取 question.id，用于命名裁剪图片

            # 根据坐标裁剪题目图片
            if crop_source_path and coordinate:
                cut_filename = f"cut_task{task_id}_q{new_question.id}.jpg"
                cut_path = os.path.join(CUT_DIR, cut_filename)
                if _crop_question_image(crop_source_path, coordinate, cut_path):
                    new_question.question_image = cut_path

            saved_count += 1

    db.commit()
    return saved_count


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
    Celery 后台任务：对图片进行 OCR 识别 + 切题，结果存入 question_results 表
    切题时优先尝试 photo 类型，若 subject_list 为空则自动回退 scan 类型重试
    同时根据坐标从 processed_image 裁剪出题目图片保存到 data/cut_images/

    :param self: Celery任务实例自身 (为了获取 request.id)
    :param assignment_task_id: 数据库中的作业任务ID
    :param processed_image_path: 清洗后图片的物理路径（用于OCR文字识别 + 裁剪源图）
    :param raw_image_path: 原始图片的物理路径（用于题目切割，二值化图片切题效果差）
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

        # 决定切题用哪张图片：优先原始图片，其次清洗后的图片
        cut_image_path = raw_image_path if raw_image_path and os.path.exists(raw_image_path) else processed_image_path
        crop_source_path = processed_image_path if processed_image_path and os.path.exists(processed_image_path) else None

        # 步骤1：整页试卷识别
        with open(ocr_image_path, "rb") as f:
            image_body = f.read()
        ocr_type = "scan" if ocr_image_path == processed_image_path else "photo"
        ocr_result = page_recognize(body=image_body, image_type=ocr_type)
        if not ocr_result or not ocr_result.get("content"):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OCR整页识别返回空结果",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        # 步骤2：试卷切题（优先 photo 类型，subject_list 为空则用 scan 重试）
        with open(cut_image_path, "rb") as f:
            cut_body = f.read()

        cut_result = None
        used_img_type = None
        for try_img_type in ["photo", "scan"]:
            cut_result = paper_cut(body=cut_body, image_type=try_img_type, output_oricoord=True)
            if cut_result:
                page_list = cut_result.get("page_list", [])
                has_subjects = any(
                    len(p.get("subject_list", [])) > 0 for p in page_list
                )
                if has_subjects:
                    used_img_type = try_img_type
                    break
                print(f"切题 image_type={try_img_type} 未找到题目，尝试下一个...")

        if not cut_result or not cut_result.get("page_list"):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OCR切题返回空结果",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        print(f"切题成功：image_type={used_img_type}")

        # 步骤3：将切题结果写入 question_results 表，同时裁剪题目图片
        os.makedirs(CUT_DIR, exist_ok=True)
        with SyncSessionLocal() as db:
            saved_count = _save_question_results(
                db, assignment_task_id, cut_result,
                crop_source_path=crop_source_path,
            )

        # 更新任务状态为完成
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

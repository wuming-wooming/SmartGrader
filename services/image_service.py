"""
图像处理服务模块
提供图片的本地清洗、去黑边、文字增强等功能, 该模块的方法将被 Celery Worker 在后台进程中执行

日期： 2026/5/15

创建者：周康哲
"""

import os
import cv2
from sqlalchemy import select

from core.celery_app import celery_app
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from services.ocr_service import process_ocr_task


# 对输入图片进行 OpenCV 清洗处理, 并保存到输出路径
def _do_opencv_cleaning(input_path: str, output_path: str) -> bool:
    """
    对输入图片进行 OpenCV 清洗处理, 并保存到输出路径
    处理流程：灰度化 -> 阈值二值化找轮廓 -> 裁剪黑边 -> 自适应阈值增强文字

    :param input_path: 输入图片路径
    :param output_path: 输出图片路径
    :return: 如果处理成功则返回 True, 否则返回 False
    """
    if not os.path.exists(input_path):
        return False
    img = cv2.imread(input_path)
    if img is None:
        return False

    # 灰度化（先将彩色的原图转换为灰度图，亮度值0-255）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 自适应阈值二值化找出所有深色内容（文字、线条）
    # blockSize=51(C=10)：较大的窗口确保即使是较粗的笔画也能被完整识别，不会变成空心轮廓
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 10
    )

    # 膨胀操作：使用较大的核，强制将相近的文字段落、题目连通成大块区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    dilated = cv2.dilate(binary, kernel, iterations=2)

    # 查找所有连通区域
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        img_h, img_w = gray.shape
        img_area = img_w * img_h
        valid_contours = []

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # 使用外接矩形面积过滤：
            # 1. 过滤掉过小的噪点 (> 0.0005)
            # 2. 过滤掉图像边缘/整图边框的伪轮廓 (< 0.90)
            if w * h > img_area * 0.0005 and w * h < img_area * 0.90:
                valid_contours.append(c)

        if valid_contours:
            x_min = min([cv2.boundingRect(c)[0] for c in valid_contours])
            y_min = min([cv2.boundingRect(c)[1] for c in valid_contours])
            x_max = max(
                [
                    cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2]
                    for c in valid_contours
                ]
            )
            y_max = max(
                [
                    cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3]
                    for c in valid_contours
                ]
            )

            w = x_max - x_min
            h = y_max - y_min

            if w * h > img_area * 0.05 and w * h < img_area * 0.99:
                pad = 40
                pad_y = 60
                x1 = max(0, x_min - pad)
                y1 = max(0, y_min - pad_y)
                x2 = min(img_w, x_max + pad)
                y2 = min(img_h, y_max + pad_y)
                gray = gray[y1:y2, x1:x2]

    # 2. 自适应阈值增强文字 (修正为 THRESH_BINARY 保持白底黑字)
    enhanced = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 10
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, enhanced)
    return True


# 同步更新数据库中的任务状态和异步日志状态 (专为 Celery Worker 设计)
def _update_db_status(
    assignment_task_id: int,
    celery_task_id: str,
    status: int,
    processed_file: str = None,
    error: str = None,
):
    """
    同步更新数据库中的任务状态和异步日志状态

    :param assignment_task_id: 作业主表记录ID
    :param celery_task_id: Celery 分配的任务UUID
    :param status: 状态码 (1=处理中, 2=完成, 3=失败)
    :param processed_file: 处理后的图片相对路径URL
    :param error: 错误信息
    :return: None
    """
    with SyncSessionLocal() as db:
        # 更新作业主表(AssignmentTask)
        assignment_task = db.get(AssignmentTask, assignment_task_id)
        if assignment_task:
            assignment_task.task_status = status
            if processed_file:
                assignment_task.processed_file = processed_file
            if error:
                assignment_task.error_msg = error

        # 更新或创建异步日志表 (AsyncTask)
        stmt = select(AsyncTask).where(AsyncTask.celery_task_id == celery_task_id)
        result = db.execute(stmt)
        aysnc_log = result.scalars().first()
        if aysnc_log:
            aysnc_log.status = status
            if error:
                aysnc_log.error_detail = error
        else:
            new_log = AsyncTask(
                assignment_task_id=assignment_task_id,
                celery_task_id=celery_task_id,
                status=status,
                error_detail=error if error else None,
            )
            db.add(new_log)

        db.commit()


# Celery 后台任务：执行图像清洗，并更新数据库状态
@celery_app.task(bind=True, name="process_homework_image_task")
def process_homework_image_task(
    self, assignment_task_id: int, input_path: str, output_path: str, processed_url: str
):
    """
    Celery 后台任务：执行图像清洗，并更新数据库状态
    该函数由 Celery Worker 在独立进程中调用

    :param self: Celery任务实例自身 (为了获取 request.id)
    :param assignment_task_id: 刚创建的数据库任务ID
    :param input_path: 硬盘上的原图路径
    :param output_path: 清洗后图片要保存的硬盘路径
    :param processed_url: 清洗后图片对前端暴露的相对URL
    """
    try:
        # 开始执行，更新状态为 "处理中"
        _update_db_status(
            assignment_task_id,
            self.request.id,
            status=1,
        )

        # 执行 OpenCV 清洗处理
        success = _do_opencv_cleaning(input_path, output_path)

        # 根据结果更新数据库
        if success:
            # 处理成功，更新状态为 "完成"
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=2,
                processed_file=processed_url,
            )
            # 图片清洗完成后，自动触发OCR识别与切题
            # 传入raw图片用于切题（二值化图片切题效果差），处理后的图片用于OCR识别
            process_ocr_task.delay(
                assignment_task_id=assignment_task_id,
                processed_image_path=output_path,
                raw_image_path=input_path,
            )
            return {"status": "success", "task_id": assignment_task_id}
        else:
            # 处理失败，更新状态为 "失败"
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OpenCV清洗算法失败：无法读取或处理图像",
            )
            return {"status": "failed", "task_id": assignment_task_id}
    except Exception as e:
        # 发生崩溃等严重异常时，记录错误日志
        try:
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"处理过程发生异常:{str(e)}",
            )
        except Exception as inner_e:
            print(f"更新数据库状态失败: {inner_e}")
        raise e

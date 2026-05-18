"""
OCR试卷识别与切题路由模块

日期： 2026/5/18

创建者：罗東明
"""

from fastapi import APIRouter, Depends

from core.auth import get_current_user
from core.database import get_db
from models.user import User
from schemas.ocr_schemas import OCRResponse
from services.ocr_service import process_ocr_task

# 创建路由器实例
router = APIRouter(prefix="/ocr", tags=["OCR"])


class OCRRouter:
    """OCR操作路由类（按SmartGrader规范）"""

    @staticmethod
    @router.post("/process", response_model=OCRResponse)
    async def trigger_ocr(
        task_id: int,
        db=Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        手动触发 OCR 识别与切题处理
        根据作业任务ID找到对应的清洗后图片，提交到Celery进行OCR识别+切题

        - **task_id**: 作业任务ID（来自上传图片返回的 task_id）
        """
        # 提交OCR任务到Celery Worker
        process_ocr_task.delay(assignment_task_id=task_id)

        return OCRResponse(
            status="submitted",
            task_id=task_id,
            message="OCR任务已提交到后台处理",
        )

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
from tasks.ocr_tasks import process_ocr_task

# 创建路由器实例
router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/process", response_model=OCRResponse, summary="手动触发OCR识别与切题")
async def trigger_ocr(
    task_id: int,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    手动触发 OCR 识别与切题处理.
    通常在图片清洗完成后自动触发, 也可手动调用此接口重试OCR.

    - **task_id**: 作业任务ID（来自上传图片返回的 task_id）
    """
    process_ocr_task.delay(assignment_task_id=task_id)

    return OCRResponse(
        status="submitted",
        task_id=task_id,
        message="OCR任务已提交到后台处理",
    )

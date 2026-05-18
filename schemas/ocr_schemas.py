"""
OCR识别与切题 Pydantic 数据模型

日期： 2026/5/18

创建者：罗東明
"""

from pydantic import BaseModel


class OCRResponse(BaseModel):
    """OCR识别/切题响应模型"""
    status: str
    task_id: int
    questions_saved: int = 0
    message: str = ""

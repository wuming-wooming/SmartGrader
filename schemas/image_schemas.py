"""
图像处理与作业任务相关的数据模型 (Schema)

日期： 2026/5/15

创建者：周康哲
"""

from pydantic import BaseModel
from typing import Optional

# 上传并清洗图片后的响应模型
class ImageProcessResponse(BaseModel):
    task_id: int
    message: str
    raw_image_url: str
    processed_image_url: Optional[str] = None
    task_status: int


class ProcessedImageResponse(BaseModel):
    """获取处理好的图片响应"""
    task_id: int
    processed_image_url: str


# ===========================================================================
# 切题图片展示
# ===========================================================================
class CutImageItem(BaseModel):
    """单道切题图片 + 元数据"""
    question_id: int
    question_index: int
    page_num: int
    subject: str
    question_text: str | None = None
    image_url: str | None = None
    coordinate: dict | None = None

    model_config = {"from_attributes": True}


class CutImageListResponse(BaseModel):
    """切题图片列表响应"""
    task_id: int
    total: int
    cuts: list[CutImageItem]


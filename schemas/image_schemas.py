"""
图像处理与作业任务相关的数据模型 (Schema)

日期： 2026/5/15

创建者：周康哲
"""

from pydantic import BaseModel
from typing import Optional

#上传并清洗图片后的响应模型
class ImageProcessResponse(BaseModel):
    task_id: int
    message: str
    raw_image_url: str
    processed_image_url: Optional[str] = None
    task_status: int


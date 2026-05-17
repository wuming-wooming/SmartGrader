"""
OCR 数据校验服务 —— 校验组员 OCR 模块产出的数据

创建者：童天宇
"""
import logging

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class _OCRItemValidator(BaseModel):
    page_num: int = Field(ge=1)
    question_index: int = Field(ge=0)
    subject: str = Field(min_length=1, max_length=20)
    question_text: str | None = None
    question_image: str | None = None
    coordinate: dict | None = None
    full_score: float = Field(gt=0)


class OCRService:
    """OCR 数据校验与标准化"""

    @staticmethod
    def validate_ocr_data(ocr_data: list[dict]) -> list[dict]:
        if not ocr_data:
            raise ValueError("OCR 数据列表为空")

        validated = []
        for i, item in enumerate(ocr_data):
            try:
                v = _OCRItemValidator(**item)
            except ValidationError as e:
                logger.error("OCR 数据第 %d 项校验失败: %s", i, e)
                raise ValueError(f"OCR 数据第 {i} 项不合法: {e}")

            subject_map = {"数学": "math", "语文": "chinese", "英语": "english"}
            subject = v.subject.strip()
            subject = subject_map.get(subject, subject.lower())

            validated.append({
                "page_num": v.page_num,
                "question_index": v.question_index,
                "subject": subject,
                "question_text": v.question_text or "",
                "question_image": v.question_image,
                "coordinate": v.coordinate,
                "full_score": v.full_score,
            })

        return validated

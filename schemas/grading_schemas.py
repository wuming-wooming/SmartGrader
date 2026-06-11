"""
批阅相关 Pydantic 模型

创建者：童天宇
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ===========================================================================
# OCR 数据（组员模块提供）
# ===========================================================================
class OCRDataItem(BaseModel):
    """单题 OCR 数据"""
    page_num: int = Field(ge=1, description="页码（从1开始）")
    question_index: int = Field(ge=0, description="题目在页内的序号（从0开始）")
    subject: str = Field(min_length=1, max_length=20, description="学科：math/chinese/english")
    question_text: str | None = Field(None, description="OCR识别的题目文本")
    question_image: str | None = Field(None, description="题目裁切图片OSS地址")
    coordinate: dict | None = Field(None, description="坐标包围盒")
    full_score: float = Field(gt=0, description="本题满分")

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, v: str) -> str:
        mapping = {"数学": "math", "语文": "chinese", "英语": "english"}
        return mapping.get(v.strip(), v.strip().lower())


# ===========================================================================
# 提交批阅
# ===========================================================================
class SubmitTaskRequest(BaseModel):
    """提交批阅任务请求"""
    task_type: int = Field(ge=1, le=3, description="1=单题, 2=整页, 3=多页")
    total_pages: int = Field(default=1, ge=1)
    original_file: str = Field(description="原始图片OSS根路径")
    processed_file: str | None = Field(None, description="预处理后图片OSS根路径")
    questions: list[OCRDataItem] = Field(min_length=1, description="OCR数据列表")


class SubmitTaskResponse(BaseModel):
    """提交批阅任务响应"""
    assignment_task_id: int
    celery_task_id: str
    status: int = 0


# ===========================================================================
# 任务状态查询
# ===========================================================================
class TaskStatusResponse(BaseModel):
    assignment_task_id: int
    task_status: int
    task_status_label: str
    celery_task_id: str
    async_status: int
    retry_count: int
    error_msg: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


# ===========================================================================
# 批阅结果
# ===========================================================================
class QuestionResultItem(BaseModel):
    question_index: int
    page_num: int
    subject: str
    question_text: str | None = None
    question_image: str | None = None
    is_correct: int
    score: float
    full_score: float
    error_reason: str | None = None
    correct_answer: str | None = None
    comment: str | None = None

    model_config = {"from_attributes": True}


class ReportItem(BaseModel):
    total_score: float
    max_total_score: float
    correct_count: int
    total_questions: int
    subject_list: list = []
    page_count: int
    summary: str | None = None
    suggestion: str | None = None

    model_config = {"from_attributes": True}


class TaskResultResponse(BaseModel):
    assignment_task_id: int
    task_status: int
    task_type: int
    questions: list[QuestionResultItem]
    report: ReportItem | None = None


# ===========================================================================
# 任务列表
# ===========================================================================
class TaskListItem(BaseModel):
    assignment_task_id: int
    task_type: int
    total_pages: int
    task_status: int
    task_status_label: str
    created_at: datetime
    finished_at: datetime | None = None
    total_questions: int | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskListItem]
    total: int
    limit: int
    offset: int

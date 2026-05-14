"""
规范数据库表实体类导入

日期： 2026/5/14

创建者：童天宇
"""

# 导出所有模型
from .assignment_task import AssignmentTask
from .async_task import AsyncTask
from .question_result import QuestionResult
from .report import Report
from .user import User

# 定义 __all__，让导入更规范
__all__ = [
    "User",
    "QuestionResult",
    "Report",
    "AssignmentTask",
    "AsyncTask"
]

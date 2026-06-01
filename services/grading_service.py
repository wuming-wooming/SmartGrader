"""
逐题批阅服务 —— 调用 LangChain LLM 进行单题评分
使用策略模式管理批改路径（纯文本 / 多模态）

创建者：童天宇
"""
import asyncio
import logging

from core.config import LLM_CONCURRENCY
from services.llm.grading_strategies import GradingStrategy, GradingStrategyFactory

logger = logging.getLogger(__name__)


class GradingService:
    """单题 LLM 批阅服务"""

    def __init__(self, strategy: GradingStrategy | None = None):
        self._semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
        self._strategy = strategy or GradingStrategyFactory.get_strategy()

    async def grade_question(self, question_data: dict) -> dict:
        """对单道题目执行 LLM 批阅，返回标准化结果字典"""
        async with self._semaphore:
            return await self._strategy.grade(question_data)

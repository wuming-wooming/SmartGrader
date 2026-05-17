"""
逐题批阅服务 —— 调用 LangChain LLM 进行单题评分

创建者：童天宇
"""
import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import LLM_CONCURRENCY
from services.llm.llm_provider import LLMProvider
from services.llm.output_parser import GradingResult, parse_grading_result
from services.llm.prompt_templates import get_grading_prompt

logger = logging.getLogger(__name__)


class GradingService:
    """单题 LLM 批阅服务"""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

    async def grade_question(self, question_data: dict) -> dict:
        """对单道题目执行 LLM 批阅，返回标准化结果字典"""
        async with self._semaphore:
            return await self._do_grade(question_data)

    async def _do_grade(self, question_data: dict) -> dict:
        subject = question_data.get("subject", "math")
        question_text = question_data.get("question_text", "")
        full_score = float(question_data.get("full_score", 10.0))

        system_prompt, user_template = get_grading_prompt(subject)
        user_prompt = user_template.format(
            full_score=full_score,
            question_text=question_text,
        )

        model = LLMProvider.get_model(temperature=0.1)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await model.ainvoke(messages)
        result: GradingResult = parse_grading_result(response.content, full_score)

        logger.info(
            "题目批阅完成 subject=%s score=%s/%s is_correct=%d",
            subject, result.score, full_score, result.is_correct,
        )

        return {
            "is_correct": result.is_correct,
            "score": result.score,
            "error_reason": result.error_reason,
            "correct_answer": result.correct_answer,
            "comment": result.comment,
        }

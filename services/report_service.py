"""
报告生成服务 —— 汇总题目批改结果，调用 LLM 生成评估报告

创建者：童天宇
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.assignment_task import AssignmentTask
from models.question_result import QuestionResult
from models.report import Report
from services.llm.llm_provider import LLMProvider
from services.llm.output_parser import parse_report_suggestion
from services.llm.prompt_templates import REPORT_SYSTEM_PROMPT, REPORT_USER_PROMPT

logger = logging.getLogger(__name__)


class ReportService:
    """批阅报告生成服务"""

    async def generate_and_save_report(
        self, session: AsyncSession, assignment_task_id: int
    ) -> Report:
        task = await session.get(AssignmentTask, assignment_task_id)
        if not task:
            raise ValueError(f"AssignmentTask {assignment_task_id} 不存在")

        stmt = (
            select(QuestionResult)
            .where(QuestionResult.task_id == assignment_task_id)
            .order_by(QuestionResult.page_num, QuestionResult.question_index)
        )
        result = await session.execute(stmt)
        question_results: list[QuestionResult] = result.scalars().all()

        total_questions = len(question_results)
        correct_count = sum(1 for q in question_results if q.is_correct == 1)
        wrong_count = total_questions - correct_count
        total_score = sum(q.score for q in question_results)
        max_total_score = sum(float(q.full_score) for q in question_results)
        subjects = list(dict.fromkeys(q.subject for q in question_results))

        lines = []
        for i, q in enumerate(question_results, 1):
            lines.append(
                f"第{i}题 [{q.subject}] 得分 {q.score}/{q.full_score} "
                f"{'正确' if q.is_correct else '错误'} "
                f"错误原因: {q.error_reason or '无'}"
            )
        question_details = "\n".join(lines)

        user_prompt = REPORT_USER_PROMPT.format(
            total_questions=total_questions,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_score=total_score,
            max_total_score=max_total_score,
            subjects=", ".join(subjects),
            question_details=question_details,
        )

        model = LLMProvider.get_model(temperature=0.3)
        messages = [
            SystemMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = await model.ainvoke(messages)
        suggestion = parse_report_suggestion(response.content)

        report = Report(
            task_id=assignment_task_id,
            user_id=task.user_id,
            total_score=total_score,
            max_total_score=max_total_score,
            correct_count=correct_count,
            total_questions=total_questions,
            subject_list=subjects,
            page_count=task.total_pages,
            task_type=task.task_type,
            task_status=2,
            summary=suggestion.summary,
            suggestion=suggestion.suggestion,
        )
        session.add(report)
        await session.commit()

        logger.info("报告生成完成 task_id=%d total=%.1f/%.1f", assignment_task_id, total_score, max_total_score)
        return report

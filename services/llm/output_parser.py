"""
LLM 输出解析器 —— 从 LLM 响应中提取结构化 JSON

创建者：童天宇
"""
import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GradingResult:
    is_correct: int
    score: float
    error_reason: str
    correct_answer: str
    comment: str


@dataclass
class ReportSuggestion:
    summary: str
    suggestion: str


def _extract_json(text: str) -> dict:
    """从 LLM 响应中健壮地提取 JSON 对象"""
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_match:
        text = code_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # # 处理LaTeX格式中的'\'，防止JSON解析失败
    # text = re.sub(r"\\", "\\\\", text)

    # 替换反斜杠，防止JSON解析失败
    text = re.sub(r"\\", "※", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("JSON 解析失败，原始文本前200字符: %s", text[:200])
        raise ValueError(f"无法从 LLM 响应中解析 JSON: {text[:500]}")


def parse_grading_result(raw_text: str, full_score: float) -> GradingResult:
    """解析 LLM 批阅结果"""
    data = _extract_json(raw_text)

    score = float(data.get("score", 0))
    score = max(0.0, min(score, full_score))

    is_correct = int(data.get("is_correct", 0))
    if score == full_score:
        is_correct = 1

    return GradingResult(
        is_correct=is_correct,
        score=score,
        # 还原反斜杠
        error_reason=str(data.get("error_reason", "").replace("※", "\\")),
        correct_answer=str(data.get("correct_answer", "").replace("※", "\\")),
        comment=str(data.get("comment", "").replace("※", "\\")),
    )


def parse_report_suggestion(raw_text: str) -> ReportSuggestion:
    """解析 LLM 报告建议"""
    data = _extract_json(raw_text)
    return ReportSuggestion(
        summary=str(data.get("summary", "")),
        suggestion=str(data.get("suggestion", "")),
    )

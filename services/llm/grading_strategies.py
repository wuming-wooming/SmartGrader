"""
LLM 批改策略模块
使用策略模式封装批改路径选择，使用 LCEL 管理 Prompt 链

- TextOnlyGradingStrategy: 纯文本批改
- MultimodalGradingStrategy: 多模态批改（文本 + 题目图片）
- GradingStrategyFactory: 根据配置选择策略

日期： 2026/5/22
"""
import base64
import logging
import os
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, SystemMessage

from core import config
from services.llm.llm_provider import LLMProvider
from services.llm.prompt_templates import (
    MULTIMODAL_USER_PROMPT,
    BAIDU_REVIEW_USER_PROMPT,
    _safe_format,
    get_grading_prompt,
)

logger = logging.getLogger(__name__)


def _normalize_grading_result(raw: dict, full_score: float) -> dict:
    """将 LLM 原始输出标准化为业务字典"""
    score = float(raw.get("score", 0))
    score = max(0.0, min(score, full_score))

    is_correct = int(raw.get("is_correct", 0))
    if score == full_score:
        is_correct = 1

    return {
        "is_correct": is_correct,
        "score": score,
        "error_reason": str(raw.get("error_reason", "").replace("※", "\\")),
        "correct_answer": str(raw.get("correct_answer", "").replace("※", "\\")),
        "comment": str(raw.get("comment", "").replace("※", "\\")),
    }


def _parse_json_response(text: str) -> dict:
    """从 LLM 响应中解析 JSON（复用现有解析器的健壮逻辑）"""
    from services.llm.output_parser import _extract_json
    return _extract_json(text)


def _encode_image_as_data_url(image_path: str) -> str | None:
    """将本地图片编码为 base64 data URL"""
    try:
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
        mime = mime_map.get(ext, "jpeg")
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"
    except Exception:
        logger.warning("图片编码失败: %s", image_path, exc_info=True)
        return None

def _make_image_data(image_path: str, user_prompt: str) -> list[dict]:
    human_content: list[dict] = [
        {"type": "text", "text": user_prompt},
    ]
    if image_path and os.path.exists(image_path):
        image_url = _encode_image_as_data_url(image_path)
        if image_url:
            human_content.append({
                "type": "image_url",
                "image_url": {"url": image_url},
            })
    return human_content

# ======================== 策略基类 ========================


class GradingStrategy(ABC):
    """批改策略抽象基类"""

    @abstractmethod
    async def grade(self, question_data: dict) -> dict:
        """执行批阅，返回标准化结果 dict"""


# ======================== 纯文本批改策略 ========================


class TextOnlyGradingStrategy(GradingStrategy):
    """纯文本批改策略"""

    async def grade(self, question_data: dict) -> dict:
        subject = question_data.get("subject", "default")
        question_text = question_data.get("question_text", "")
        full_score = float(question_data.get("full_score", 10.0))

        system_prompt, user_template = get_grading_prompt(subject)
        user_prompt = _safe_format(
            user_template,
            subject=subject,
            full_score=full_score,
            question_text=question_text,
        )

        model = LLMProvider.get_model(temperature=0.1)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await model.ainvoke(messages)
        raw = _parse_json_response(response.content)

        logger.info(
            "纯文本批阅完成 subject=%s score=%s/%s",
            subject, raw.get("score", 0), full_score,
        )
        return _normalize_grading_result(raw, full_score)


# ======================== 多模态批改策略 ========================


class MultimodalGradingStrategy(GradingStrategy):
    """
    多模态批改策略：文本 + 题目裁切图片
    将题目图片以 base64 data URL 形式携带在 HumanMessage 中
    """

    async def grade(self, question_data: dict) -> dict:
        subject = question_data.get("subject", "default")
        question_text = question_data.get("question_text", "")
        full_score = float(question_data.get("full_score", 10.0))
        image_path = question_data.get("question_image", "")

        system_prompt, _ = get_grading_prompt(subject)
        user_prompt = _safe_format(
            MULTIMODAL_USER_PROMPT,
            subject=subject,
            full_score=full_score,
            question_text=question_text,
        )

        # 构建多模态 HumanMessage
        human_content = _make_image_data(image_path, user_prompt)

        model = LLMProvider.get_model(temperature=0.1)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content),
        ]
        response = await model.ainvoke(messages)
        raw = _parse_json_response(response.content)

        logger.info(
            "多模态批阅完成 subject=%s score=%s/%s",
            subject, raw.get("score", 0), full_score,
        )
        return _normalize_grading_result(raw, full_score)

# ======================== 百度智能批阅接口LLM复核策略 ========================
class BaiduLLMGradingStrategy(GradingStrategy):
    """百度智能批阅接口LLM复核策略"""
    async def grade(self, question_data: dict) -> dict:
        subject = question_data.get("subject", "default")
        # question_text = question_data.get("question_text", "")
        full_score = float(question_data.get("full_score", 10.0))
        is_correct = question_data.get("is_correct", 0) == 1
        comment = question_data.get("comment", "")
        image_path = question_data.get("question_image", "")

        system_prompt, _ = get_grading_prompt(subject)
        user_prompt = _safe_format(
            BAIDU_REVIEW_USER_PROMPT,
            subject=subject,
            full_score=full_score,
            is_correct=is_correct,
            comment=comment,
        )

        # 构建多模态 HumanMessage
        human_content = _make_image_data(image_path, user_prompt)

        model = LLMProvider.get_model(temperature=0.1)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content),
        ]
        response = await model.ainvoke(messages)
        raw = _parse_json_response(response.content)

        logger.info(
            "LLM复核批阅完成 subject=%s score=%s/%s",
            subject, raw.get("score", 0), full_score,
        )
        return _normalize_grading_result(raw, full_score)


# ======================== 策略工厂 ========================


class GradingStrategyFactory:
    """批改策略工厂，根据配置和数据选择策略"""

    @staticmethod
    def get_strategy(strategy_name: str | None = None,
                     question_data: dict | None = None) -> GradingStrategy:
        """
        选择策略：
        1. 显式传入 strategy_name → 直接使用
        2. 全局配置 LLM_GRADING_STRATEGY=multimodal → 多模态
        3. 默认 → 纯文本
        """
        if strategy_name:
            if strategy_name == "multimodal":
                return MultimodalGradingStrategy()
            return TextOnlyGradingStrategy()

        # TODO: 需要斟酌如何获取到当前是百度智能批阅复核还是普通OCR切题后批阅，当前默认使用百度智能批阅复核
        if config.BAIDU_HOMEWORK_LLM_REVIEW:
            return BaiduLLMGradingStrategy()

        if config.LLM_GRADING_STRATEGY == "multimodal":
            return MultimodalGradingStrategy()

        return TextOnlyGradingStrategy()

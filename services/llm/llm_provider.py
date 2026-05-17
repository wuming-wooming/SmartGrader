"""
LLM Provider —— 封装 LangChain ChatOpenAI，支持任意 OpenAI 兼容 API

创建者：童天宇
"""
from langchain_openai import ChatOpenAI

from core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME, LLM_REQUEST_TIMEOUT


class LLMProvider:
    """LLM 实例管理器，懒加载单例"""

    _instance: ChatOpenAI | None = None

    @classmethod
    def get_model(
        cls, temperature: float = 0.1, model_name: str | None = None
    ) -> ChatOpenAI:
        if cls._instance is None or model_name is not None:
            cls._instance = ChatOpenAI(
                model=model_name or LLM_MODEL_NAME,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                temperature=temperature,
                request_timeout=LLM_REQUEST_TIMEOUT,
                max_retries=2,
            )
        return cls._instance

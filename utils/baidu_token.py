"""
百度云 access_token 管理器
提供模块级缓存的 token 获取与自动刷新，供 BaiduOCREngine 和 BaiduHomeworkGradingAPI 共享

日期： 2026/5/22
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"


class BaiduTokenManager:
    """百度云 access_token 管理器（实例级缓存）"""

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key
        self._cached_token: str | None = None
        self._token_expires_at: float = 0

    def get_token(self) -> str:
        """确保 token 有效，过期前 1 小时自动刷新"""
        if self._cached_token is None or time.time() > self._token_expires_at - 3600:
            self._cached_token, self._token_expires_at = self._fetch_token()
        return self._cached_token

    def invalidate(self):
        """强制下次调用 get_token 时重新获取"""
        self._cached_token = None

    def _fetch_token(self) -> tuple[str, float]:
        """通过 AK/SK 换取 access_token，返回 (token, 过期时间戳)"""
        params = {
            "grant_type": "client_credentials",
            "client_id": self._api_key,
            "client_secret": self._secret_key,
        }
        resp = requests.post(TOKEN_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"获取百度云 access_token 失败: {data}")
        expires_at = time.time() + data.get("expires_in", 2592000)
        logger.info("百度云 access_token 已刷新，有效期至 %s",
                     time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expires_at)))
        return data["access_token"], expires_at

"""
OCR 引擎适配器模块
提供统一的 OCR 引擎抽象接口，支持阿里云和百度云两种实现
通过配置 OCR_ENGINE 切换引擎

日期： 2026/5/20
"""
import base64
import json
import logging
import random
import time
import urllib.parse
from abc import ABC, abstractmethod

import requests

from core import config
from utils.baidu_token import BaiduTokenManager

logger = logging.getLogger(__name__)


class BaseOCREngine(ABC):
    """OCR 引擎抽象基类"""

    @abstractmethod
    def page_recognize(self, image_data: bytes, **kwargs) -> dict:
        """
        整页试卷识别，返回全文 OCR 结果

        :param image_data: 图片二进制数据
        :return: {"content": "识别出的全文文本"}
        """
        ...

    @abstractmethod
    def paper_cut(self, image_data: bytes, **kwargs) -> dict:
        """
        试卷切题识别，返回结构化题目列表

        :param image_data: 图片二进制数据
        :return: {"part_info": [{"part_title": "", "subject_list": [...]}], "page_id": 1}
        """
        ...


# ======================== 阿里云引擎 ========================


class AliyunOCREngine(BaseOCREngine):
    """阿里云 OCR 引擎，封装 RecognizeEduPaperOcr / RecognizeEduPaperStructed / RecognizeEduPaperCut"""

    def __init__(self):
        from alibabacloud_ocr_api20210707.client import Client as OcrClient
        from alibabacloud_tea_openapi import models as open_api_models

        aliyun_config = open_api_models.Config(
            access_key_id=config.ALIBABA_CLOUD_ACCESS_KEY_ID,
            access_key_secret=config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            endpoint=config.ALIBABA_CLOUD_ENDPOINT,
        )
        self._client = OcrClient(aliyun_config)

    def page_recognize(
        self,
        image_data: bytes,
        image_type: str = "photo",
        subject: str = "default",
        output_oricoord: bool = False,
        **kwargs,
    ) -> dict:
        from alibabacloud_ocr_api20210707.models import RecognizeEduPaperOcrRequest

        request = RecognizeEduPaperOcrRequest(
            image_type=image_type,
            subject=subject,
            output_oricoord=output_oricoord,
        )
        request.body = image_data
        response = self._client.recognize_edu_paper_ocr(request)
        return json.loads(response.body.data)

    def paper_cut(
        self,
        image_data: bytes,
        subject: str = "default",
        need_rotate: bool = True,
        output_oricoord: bool = True,
        cut_type: str = "question",
        image_type: str = "photo",
        **kwargs,
    ) -> dict:
        from alibabacloud_ocr_api20210707.models import (
            RecognizeEduPaperCutRequest,
            RecognizeEduPaperStructedRequest,
        )

        # 优先尝试精细版结构化切题
        try:
            request = RecognizeEduPaperStructedRequest(
                subject=subject,
                need_rotate=need_rotate,
                output_oricoord=output_oricoord,
            )
            request.body = image_data
            response = self._client.recognize_edu_paper_structed(request)
            result = json.loads(response.body.data)
            if result and result.get("part_info"):
                has_subjects = any(
                    len(p.get("subject_list", [])) > 0
                    for p in result["part_info"]
                )
                if has_subjects:
                    return result
        except Exception as e:
            logger.warning("RecognizeEduPaperStructed 失败，回退到 RecognizeEduPaperCut: %s", e)

        # 回退：旧版切题
        for try_img_type in [image_type, "photo", "scan"]:
            try:
                request = RecognizeEduPaperCutRequest(
                    cut_type=cut_type,
                    image_type=try_img_type,
                    subject=subject,
                    output_oricoord=output_oricoord,
                )
                request.body = image_data
                response = self._client.recognize_edu_paper_cut(request)
                result = json.loads(response.body.data)
                page_list = result.get("page_list", [])
                has_subjects = any(
                    len(p.get("subject_list", [])) > 0 for p in page_list
                )
                if has_subjects:
                    return result
            except Exception as e:
                logger.warning("RecognizeEduPaperCut(%s) 失败: %s", try_img_type, e)

        raise RuntimeError("所有阿里云切题方案均返回空结果")


# ======================== 百度云引擎 ========================


class BaiduOCREngine(BaseOCREngine):
    """百度云 OCR 引擎，通过 HTTP API 调用 paper_cut_edu / doc_analysis 接口"""

    PAPER_CUT_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu"
    DOC_ANALYSIS_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis"

    def __init__(self):
        self._token_mgr = BaiduTokenManager(
            config.BAIDU_CLOUD_API_KEY,
            config.BAIDU_CLOUD_SECRET_KEY,
        )

    # ---------- HTTP 请求封装 ----------

    @staticmethod
    def _encode_image(image_data: bytes) -> str:
        """图片二进制 → Base64 → urlencode"""
        b64 = base64.b64encode(image_data).decode("utf-8")
        return urllib.parse.quote_plus(b64)

    def _call_with_retry(self, url: str, data: dict, max_retries: int = 3) -> dict:
        """带指数退避重试的请求包装，处理 QPS 超限和 Token 过期"""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        last_error = None

        for attempt in range(max_retries):
            token = self._token_mgr.get_token()
            full_url = f"{url}?access_token={token}"

            try:
                resp = requests.post(full_url, data=data, headers=headers, timeout=60)
                result = resp.json()
            except requests.RequestException as e:
                logger.warning("百度云 OCR 请求网络异常 (第 %d 次): %s", attempt + 1, e)
                last_error = e
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
                continue

            error_code = result.get("error_code")
            if error_code is None or error_code == 0:
                return result

            error_msg = result.get("error_msg", str(result))

            if error_code in (110, 111):  # Token 无效或过期
                logger.warning("百度云 Token 过期，强制刷新后重试")
                self._token_mgr.invalidate()
                continue
            elif error_code == 18:  # QPS 超限
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("百度云 QPS 超限，%0.1f 秒后重试 (第 %d 次)", wait, attempt + 1)
                time.sleep(wait)
                continue
            elif error_code in (17, 19):  # 配额超限
                raise RuntimeError(f"百度云 OCR 配额超限: {error_msg}")
            else:
                raise RuntimeError(f"百度云 OCR API 错误 (error_code={error_code}): {error_msg}")

        if last_error:
            raise RuntimeError(f"百度云 OCR 请求重试耗尽 (网络异常)") from last_error
        raise RuntimeError("百度云 OCR 请求重试耗尽")

    # ---------- 接口 1：page_recognize（整页识别） ----------

    def page_recognize(self, image_data: bytes, **kwargs) -> dict:
        """
        调用 doc_analysis 接口，返回拼接后的全文文本

        :param image_data: 图片二进制数据
        :return: {"content": "全文文本"}
        """
        data = {
            "image": self._encode_image(image_data),
            "language_type": "CHN_ENG",
            "words_type": "handprint_mix",
            "detect_layout": "true",
            "detect_formula": "true",
        }
        result = self._call_with_retry(self.DOC_ANALYSIS_URL, data)

        # 转换格式：拼接所有 results[i].words.word
        results = result.get("results", [])
        lines = []
        for item in results:
            words = item.get("words", {})
            word = words.get("word", "") if isinstance(words, dict) else ""
            if word:
                lines.append(word)

        return {"content": "\n".join(lines)}

    # ---------- 接口 2：paper_cut（试卷切题） ----------

    def paper_cut(self, image_data: bytes, **kwargs) -> dict:
        """
        调用 paper_cut_edu 接口，返回与阿里云 Structed 兼容的格式

        :param image_data: 图片二进制数据
        :return: {"part_info": [...], "page_id": 1}
        """
        data = {
            "image": self._encode_image(image_data),
            "language_type": "CHN_ENG",
            "words_type": "handprint_mix",
            "splice_text": "true",
        }
        result = self._call_with_retry(self.PAPER_CUT_URL, data)

        return self._convert_cut_result(result)

    def _convert_cut_result(self, baidu_result: dict) -> dict:
        """将百度云 paper_cut_edu 响应转换为内部统一格式（兼容阿里云 Structed）"""
        qus_results = baidu_result.get("qus_result", [])
        subject_list = []

        for qus in qus_results:
            # 拼接题目文本（stem_text + subqus_text + option_text + answer_text）
            elem_text = qus.get("elem_text", {})
            text_parts = []
            for key in ("stem_text", "subqus_text", "option_text", "answer_text"):
                part = elem_text.get(key, "")
                if part:
                    text_parts.append(part)
            full_text = " ".join(text_parts)

            # 提取坐标（qus_location: 四角点 → pos_list 格式）
            qus_location = qus.get("qus_location", [])
            pos_list = []
            if qus_location and len(qus_location) >= 4:
                pos_list = [[
                    {"x": qus_location[0].get("x", 0), "y": qus_location[0].get("y", 0)},
                    {"x": qus_location[1].get("x", 0), "y": qus_location[1].get("y", 0)},
                    {"x": qus_location[2].get("x", 0), "y": qus_location[2].get("y", 0)},
                    {"x": qus_location[3].get("x", 0), "y": qus_location[3].get("y", 0)},
                ]]

            subject_list.append({
                "text": full_text,
                "pos_list": pos_list,
            })

        return {
            "part_info": [
                {
                    "part_title": "",
                    "subject_list": subject_list,
                }
            ],
            "page_id": 1,
        }


# ======================== 引擎工厂 ========================

_engine_instance: BaseOCREngine | None = None


def get_ocr_engine() -> BaseOCREngine:
    """根据配置返回 OCR 引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        engine_name = config.OCR_ENGINE.lower()
        if engine_name == "aliyun":
            _engine_instance = AliyunOCREngine()
        elif engine_name == "baidu":
            _engine_instance = BaiduOCREngine()
        else:
            raise ValueError(f"不支持的 OCR_ENGINE 配置: {config.OCR_ENGINE}，可选值: aliyun, baidu")
        logger.info("OCR 引擎已初始化: %s", type(_engine_instance).__name__)
    return _engine_instance

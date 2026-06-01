"""
百度云智能作业批改 API 适配器
提交图片 → 异步轮询 → 解析批改结果 → 返回标准化题目列表

该接口与 paper_cut_edu 不同，可一步完成切题 + 初批，
但采用异步提交+轮询模式，需处理超时和回退。

日期： 2026/5/22
"""
import base64
import json
import logging
import os
import time
import urllib.parse

import requests

from core import config
from utils.baidu_token import BaiduTokenManager

logger = logging.getLogger(__name__)

SUBMIT_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/create_task"
POLL_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/correct_edu/get_result"
CUT_DIR = "data/cut_images"

class BaiduHomeworkGradingAPI:
    """百度云智能作业批改 API 适配器"""

    def __init__(self):
        self._token_mgr = BaiduTokenManager(
            config.BAIDU_CLOUD_API_KEY,
            config.BAIDU_CLOUD_SECRET_KEY,
        )
        self._poll_timeout = config.BAIDU_HOMEWORK_POLL_TIMEOUT
        self._poll_interval = config.BAIDU_HOMEWORK_POLL_INTERVAL

    # ---------- 步骤 1：提交任务 ----------

    def submit_task(self, image_data: bytes, only_split: bool = False) -> str:
        """
        提交图片到百度智能作业批改 API

        :param image_data: 图片二进制数据
        :param only_split: True=仅切题不批改, False=端到端批改
        :return: baidu_task_id
        """
        b64 = base64.b64encode(image_data).decode("utf-8")
        payload = {
            "image": b64,
            "only_split": only_split,
        }
        headers = {"Content-Type": "application/json"}
        token = self._token_mgr.get_token()
        url = f"{SUBMIT_URL}?access_token={token}"

        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        error_code = result.get("error_code")
        if error_code and error_code != 0:
            error_msg = result.get("error_msg", str(result))
            raise RuntimeError(f"百度作业批改提交失败 (error_code={error_code}): {error_msg}")

        task_id = result.get("data", {}).get("task_id") or result.get("result", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"百度作业批改返回中未找到 task_id: {json.dumps(result, ensure_ascii=False)[:500]}")
        logger.info("百度作业批改任务已提交: %s", task_id)
        return task_id

    # ---------- 步骤 2：轮询结果 ----------

    def poll_result(self, baidu_task_id: str, timeout: int | None = None,
                    interval: float | None = None) -> dict:
        """
        轮询获取批改结果

        :param baidu_task_id: submit_task 返回的任务ID
        :param timeout: 最大等待秒数
        :param interval: 轮询间隔秒数
        :return: API 返回的完整批改结果
        :raises TimeoutError: 超时未完成
        """
        if timeout is None:
            timeout = self._poll_timeout
        if interval is None:
            interval = self._poll_interval

        headers = {"Content-Type": "application/json"}
        deadline = time.time() + timeout
        token = self._token_mgr.get_token()
        url = f"{POLL_URL}?access_token={token}"

        while time.time() < deadline:
            resp = requests.post(url, json={"task_id": baidu_task_id}, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            error_code = result.get("error_code")
            if error_code and error_code != 0:
                error_msg = result.get("error_msg", str(result))
                raise RuntimeError(f"百度作业批改查询失败 (error_code={error_code}): {error_msg}")

            # 检查是否完成
            is_all_finished = result.get("data", {}).get("isAllFinished") or result.get("result", {}).get("isAllFinished")
            # ret_code = result.get("data", {}).get("ret_code") or result.get("result", {}).get("ret_code")
            # if ret_code == 0 or self._has_result(result):
            if is_all_finished:
                logger.info("百度作业批改任务完成: %s", baidu_task_id)
                return result

            time.sleep(interval)

        raise TimeoutError(f"百度作业批改轮询超时 ({timeout}s): {baidu_task_id}")

    @staticmethod
    def _has_result(result: dict) -> bool:
        """判断响应是否包含最终结果"""
        data = result.get("data", {}) or result.get("result", {})
        # 有题目列表或批改结果即视为完成
        return bool(
            data.get("qus_result")
            or data.get("question_list")
            or data.get("questions")
        )

    # ---------- 步骤 3：解析为标准格式 ----------

    def parse_grading_result(self, raw_result: dict,
                             original_image_path: str | None = None) -> list[dict]:
        """
        将百度批改响应解析为内部标准格式

        返回 list[dict]，每个 dict 包含:
          - text: 题目文本
          - coordinate: {x1, y1, x2, y2}
          - subject_label: 学科标签
          - page_num: 页码
          - baidu_score: 百度预评分
          - baidu_is_correct: 百度判定对错
          - baidu_comment: 百度批注/解析
          - full_score: 满分
        """
        data = raw_result.get("data", {}) or raw_result.get("result", {}) or raw_result
        questions_raw = (
            data.get("imageResults")[0].get("result")
            or data.get("qus_result")
            or data.get("question_list")
            or data.get("questions")
            or []
        )

        subject = data.get("imageResults")[0].get("paperSubject")
        if subject == "":
            subject = "default"

        if not questions_raw:
            return []

        parsed = []
        for i, q in enumerate(questions_raw):
            item = self._parse_single_question(q, i + 1, original_image_path, subject)
            parsed.append(item)

        return parsed

    def _parse_single_question(self, q: dict, index: int,
                               image_path: str | None, subject: str) -> dict:
        """解析单道题目"""
        # --- 文本 ---
        # elem_text = q.get("elem_text", {})
        # text_parts = []
        # for key in ("stem_text", "subqus_text", "option_text", "answer_text", "question_text"):
        #     part = elem_text.get(key, "") or q.get(key, "")
        #     if part:
        #         text_parts.append(str(part))
        # if not text_parts:
        #     text_parts.append(q.get("question_text", "") or q.get("text", ""))
        # text = " ".join(text_parts)
        text = q.get("question", "")

        # --- 坐标 ---
        coordinate = self._extract_coordinate(q)

        # --- 学科 ---
        # subject = q.get("subject", "") or q.get("category", "") or elem_text.get("subject", "") or "default"

        # --- 页码 ---
        page_num = q.get("page_num", 1) or q.get("page_id", 1) or 1
        if isinstance(page_num, str):
            try:
                page_num = int(page_num)
            except ValueError:
                page_num = 1

        # --- 百度批改结果 ---
        grading = q.get("grading_result", {}) or q.get("correct_result", {}) or q
        baidu_score = grading.get("score", 0) or grading.get("grade_score", 0) or 0
        # baidu_is_correct = grading.get("is_correct", 0) or grading.get("correct", 0) or 0
        baidu_is_correct = q.get("correctResult", 2) == 1
        # baidu_comment = grading.get("comment", "") or grading.get("analysis", "") or grading.get("error_reason", "") or ""
        slot = q.get("slot", [])
        comment = []
        for i, slot in enumerate(slot):
            if not slot:
                continue
            comment.append(str(i + 1) + ". " + slot.get("reason", ""))
        baidu_comment = "\n".join(comment)
        full_score = q.get("full_score", 0) or q.get("total_score", 0) or grading.get("full_score", 0) or 0

        return {
            "text": text.strip(),
            "coordinate": coordinate,
            "subject_label": subject,
            "page_num": page_num,
            "baidu_score": float(baidu_score) if baidu_score else 0.0,
            "baidu_is_correct": int(baidu_is_correct),
            "baidu_comment": str(baidu_comment),
            "full_score": float(full_score) if full_score else 0.0,
        }

    @staticmethod
    def _extract_coordinate(q: dict) -> dict | None:
        """从题目中提取坐标"""

        # 尝试 questionArea
        loc = q.get("questionArea", [])[0]
        if loc:
            return {
                "x1": loc.get("left_x", 0),
                "y1": loc.get("left_y", 0),
                "x2": loc.get("right_x", 0),
                "y2": loc.get("right_y", 0)
            }

        # 尝试 qus_location（四角点）
        loc = q.get("qus_location", [])
        if loc and len(loc) >= 4:
            xs = [p.get("x", 0) for p in loc if isinstance(p, dict)]
            ys = [p.get("y", 0) for p in loc if isinstance(p, dict)]
            if xs and ys:
                return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}

        # 尝试 pos_list
        pos_list = q.get("pos_list", [])
        if pos_list and len(pos_list) > 0 and len(pos_list[0]) >= 2:
            points = pos_list[0]
            xs = [p.get("x", 0) for p in points if isinstance(p, dict)]
            ys = [p.get("y", 0) for p in points if isinstance(p, dict)]
            if xs and ys:
                return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}

        # 尝试直接坐标字段
        if all(k in q for k in ("x1", "y1", "x2", "y2")):
            return {"x1": q["x1"], "y1": q["y1"], "x2": q["x2"], "y2": q["y2"]}

        # 尝试 location 字段
        loc = q.get("location", {})
        if loc:
            if all(k in loc for k in ("left", "top", "width", "height")):
                return {
                    "x1": loc["left"], "y1": loc["top"],
                    "x2": loc["left"] + loc["width"],
                    "y2": loc["top"] + loc["height"],
                }

        return None

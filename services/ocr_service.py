"""
OCR识别与切题服务模块
提供切题结果数据后处理：坐标提取、题目拆分、图片裁剪、结果入库
OCR 引擎调用已抽象到 services/ocr_engine.py

日期： 2026/5/18

创建者：罗東明
"""
import os
import re
import logging

from pydantic import BaseModel, Field, ValidationError

import cv2

from models.question_result import QuestionResult

logger = logging.getLogger(__name__)

# 裁剪图片保存目录
CUT_DIR = "data/cut_images"

# 学科关键词检测表：用于当 API 返回空 subject 时从文本内容推断学科
_SUBJECT_DETECT_KEYWORDS = {
    "math": [
        "计算", "方程", "几何", "分数", "小数", "加减乘除", "乘除",
        "体积", "面积", "周长", "边长", "半径", "直径", "÷", "×",
        "正方形", "长方形", "三角形", "梯形", "平行", "角度", "度数",
        "千克", "克", "吨", "千米", "米", "速度", "时间", "距离",
        "乘法", "加法", "减法", "除法", "个位", "十位", "百位",
        "公鸡", "母鸡",  # 小学应用题常见
    ],
    "chinese": [
        "拼音", "词语", "句子", "作文", "阅读", "古诗", "文言文",
        "汉字", "笔画", "部首", "组词", "造句", "修辞", "比喻",
        "下列", "选词", "填空", "朗读", "课文", "作者",
    ],
    "english": [
        "单词", "英语", "字母", "发音", "拼写", "语法", "时态",
        "词汇", "句型", "翻译", "阅读理解",
    ],
    "history": [
        "鸦片战争", "太平天国", "辛亥革命", "五四运动", "洋务运动",
        "戊戌变法", "历史", "古代", "近代", "时期", "世纪",
        "革命", "战争", "运动", "起义", "王朝", "帝国",
        "某学者认为", "学者", "材料", "反映了", "体现了",
        "工业革命", "资产阶级", "无产阶级", "社会主义",
    ],
    "physics": [
        "质量", "密度", "体积", "重力", "速度", "加速度",
        "力", "牛顿", "焦耳", "压强", "浮力", "功", "功率",
        "欧姆", "电阻", "电流", "电压", "电路", "光", "声",
        "温度", "热量", "比热容", "热值",
    ],
    "chemistry": [
        "元素", "化学", "反应", "分子", "原子", "溶液", "氧气",
        "氢气", "二氧化碳", "酸碱盐", "金属", "化合价",
        "化学式", "方程式", "催化剂",
    ],
}


def _detect_subject_from_text(text: str) -> str:
    """
    从文本内容推断学科，当 API 返回空 subject_label 时作为后备方案
    通过关键词匹配（支持多个学科），返回匹配分数最高的学科名

    :param text: 题目文本内容
    :return: 学科名（如 "math", "history"），未匹配到返回 ""
    """
    if not text:
        return ""
    scores = {}
    for subject, keywords in _SUBJECT_DETECT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            scores[subject] = count
    if scores:
        best = max(scores, key=scores.get)
        return best
    return ""


def _crop_question_image(
    image_path: str, coordinate: dict, output_path: str
) -> bool:
    """
    根据坐标从原图中裁剪出题目区域并保存

    :param image_path: 原图物理路径（清洗后的图片）
    :param coordinate: 题目坐标 {"x1", "y1", "x2", "y2"}
    :param output_path: 裁剪后的图片保存路径
    :return: 成功返回 True，失败返回 False
    """
    if not os.path.exists(image_path):
        return False
    img = cv2.imread(image_path)
    if img is None:
        return False

    h, w = img.shape[:2]
    x1 = max(0, int(coordinate.get("x1", 0)))
    y1 = max(0, int(coordinate.get("y1", 0)))
    x2 = min(w, int(coordinate.get("x2", w)))
    y2 = min(h, int(coordinate.get("y2", h)))

    if x2 <= x1 or y2 <= y1:
        return False

    cropped = img[y1:y2, x1:x2]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, cropped)
    return True


def _save_question_results(
    db, task_id: int, cut_result: dict, crop_source_path: str = None,
    ocr_content: str = None,
) -> int:
    """
    将切题结果逐题写入 question_results 表
    兼容两种格式：
      - RecognizeEduPaperStructed: {"part_info": [{"subject_list": [...], ...}]}
      - RecognizeEduPaperCut:     {"page_list": [{"subject_list": [...], ...}]}
    同时根据坐标从 crop_source_path 裁剪出题目图片存入 data/cut_images/

    每个 subject 从 pos_list（或 content_list_info.pos）中提取坐标
    如果切题结果中题目数偏少但 ocr_content 较长，
    则使用 page_recognize 全文作为文本源并执行后处理拆分

    :param db: 同步数据库会话
    :param task_id: 关联的作业任务ID
    :param cut_result: 阿里云切题接口返回的原始字典
    :param crop_source_path: 用于裁剪的原图物理路径（清洗后图片），为 None 则不裁剪
    :param ocr_content: 可选的 page_recognize 全文，用于辅助拆分
    :return: 入库的题目数量
    """
    # 兼容两种响应格式：Structed 使用 part_info，Cut 使用 page_list
    containers = []
    if cut_result.get("part_info"):
        # RecognizeEduPaperStructed 格式
        for part in cut_result["part_info"]:
            part_title = part.get("part_title", "")
            subject_list = part.get("subject_list", [])
            for subj in subject_list:
                # 从 pos_list 取坐标（第一组多边形 = 题目边界框）
                coordinate = _extract_coordinate(subj.get("pos_list", []))
                text = subj.get("text", "")
                containers.append({
                    "page_num": cut_result.get("page_id", 1),
                    "text": text,
                    "coordinate": coordinate,
                    "subject_label": part_title,
                })
    elif cut_result.get("page_list"):
        # RecognizeEduPaperCut 格式（旧版备选）
        for page in cut_result["page_list"]:
            page_num = page.get("doc_index", 1)
            for subj in page.get("subject_list", []):
                coordinate = None
                content_list = subj.get("content_list_info", [])
                if content_list:
                    pos_list = content_list[0].get("pos", [])
                    if pos_list and len(pos_list) >= 2:
                        xs = [p.get("x", 0) for p in pos_list]
                        ys = [p.get("y", 0) for p in pos_list]
                        coordinate = {
                            "x1": min(xs),
                            "y1": min(ys),
                            "x2": max(xs),
                            "y2": max(ys),
                        }
                containers.append({
                    "page_num": page_num,
                    "text": subj.get("text", ""),
                    "coordinate": coordinate,
                    "subject_label": subj.get("ids", [{}])[0].get("subject", "default")
                        if subj.get("ids") else "default",
                })

    if not containers:
        return 0

    # 修复缺失题号的题目（如LaTeX开头丢题号）
    _recover_missing_numbers(containers)

    # 如果切题结果偏少但 OCR 全文明显有更多内容，用 OCR 全文替代文本作为拆分源
    if ocr_content and len(containers) <= 2 and len(ocr_content) >= 100:
        total_ocr_len = len(ocr_content)
        container_text_len = sum(len(c["text"]) for c in containers)
        # 比例差异超过 2 倍，说明切题结果遗漏了大量内容
        if total_ocr_len > container_text_len * 2:
            # 用 OCR 全文替换第一个容器的文本（保留其坐标）
            containers[0]["text"] = ocr_content
            # 如果有多余的容器（结构不完整），清除
            while len(containers) > 1:
                containers.pop()

    # 学科检测：当 API 返回的 subject_label 为空时，从文本内容推断学科
    for item in containers:
        if not item["subject_label"]:
            detected = _detect_subject_from_text(item["text"])
            if detected:
                logger.info("学科检测: '%s' -> %s (via text analysis)", item["text"][:30], detected)
                item["subject_label"] = detected

    # 后处理：拆分合并的多道题
    expanded = []
    for item in containers:
        sub_items = _split_merged_questions(item["text"], item["coordinate"])
        for sub in sub_items:
            expanded.append({
                "page_num": item["page_num"],
                "text": sub["text"],
                "coordinate": sub["coordinate"],
                "subject_label": item["subject_label"],
            })

    saved_count = 0
    for idx, item in enumerate(expanded):
        page_num = item["page_num"] if isinstance(item["page_num"], int) else 1
        new_question = QuestionResult(
            task_id=task_id,
            page_num=page_num,
            question_index=idx + 1,
            subject=item["subject_label"],
            question_text=item["text"] if item["text"] else None,
            question_image=None,  # 占位，裁剪成功后再更新
            coordinate=item["coordinate"],
            is_correct=0,  # 0=待批改
            score=0,
            full_score=0,
        )
        db.add(new_question)
        db.flush()

        # 根据坐标裁剪题目图片
        if crop_source_path and item["coordinate"]:
            # 坐标空间校验：检查坐标是否越界
            coord = item["coordinate"]
            if os.path.exists(crop_source_path):
                _validate_coordinate_bounds(coord, crop_source_path)
            cut_filename = f"cut_task{task_id}_q{new_question.id}.jpg"
            cut_path = os.path.join(CUT_DIR, cut_filename)
            if _crop_question_image(crop_source_path, item["coordinate"], cut_path):
                new_question.question_image = cut_path

        saved_count += 1

    db.commit()
    return saved_count


def _extract_coordinate(pos_list: list) -> dict | None:
    """
    从 RecognizeEduPaperStructed 的 pos_list 中提取最小外接矩形坐标
    pos_list: [[{x,y}, {x,y}, ...], ...] 每项是一个多边形（4个点）
    取第一组多边形（题目主体区域）的 x/y 极值

    :param pos_list: 多边形坐标列表
    :return: {x1, y1, x2, y2} 或 None
    """
    if not pos_list:
        return None
    # 取第一个多边形（通常代表题目主体区域）
    points = pos_list[0]
    if not points or len(points) < 2:
        return None
    xs = [p.get("x", 0) for p in points]
    ys = [p.get("y", 0) for p in points]
    return {
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }


def _recover_missing_numbers(containers: list[dict]):
    """
    修复缺失题号的题目（如 LaTeX 公式开头导致 API 丢题号）

    例如题2的文本以 $$\frac... 开头，需要恢复为 "2.$$\frac..."
    通过检测前一个题目的题号推断当前题目的期望题号

    :param containers: 按顺序排列的题目列表，原地修改
    """
    # 匹配题号前缀："1.", "2.", "(3)", "（4）" 等
    num_prefix_pattern = re.compile(r"^(\d+)[.、．）)]?")  # 标题号

    for i, item in enumerate(containers):
        text = item.get("text", "")
        if not text:
            continue

        # 检查是否以题号开头
        m = num_prefix_pattern.match(text)
        if m:
            continue  # 已有题号，跳过

        # 只有 LaTeX 开头才处理（防止误判）
        if not text.startswith("$$"):
            continue

        # 查找前一个容器的题号
        expected_num = i + 1  # 按索引推断（1-based）

        # 尝试从上一个容器找题号确认
        if i > 0:
            prev_text = containers[i - 1].get("text", "")
            pm = num_prefix_pattern.match(prev_text)
            if pm:
                prev_num = int(pm.group(1))
                if prev_num + 1 == expected_num:
                    pass  # 连续编号，确认推断正确
                else:
                    expected_num = prev_num + 1

        item["text"] = f"{expected_num}.{text}"


def _validate_coordinate_bounds(coord: dict, image_path: str):
    """
    校验坐标是否在图片范围内，超出时打印警告
    用于快速发现坐标空间不匹配的问题

    :param coord: {"x1", "x2", "y1", "y2"}
    :param image_path: 裁剪源图路径
    """
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        return
    h, w = img.shape[:2]
    warnings = []
    if coord["x1"] < 0 or coord["x1"] >= w:
        warnings.append(f"x1={coord['x1']} 超出图片宽度({w})")
    if coord["x2"] <= 0 or coord["x2"] > w:
        warnings.append(f"x2={coord['x2']} 超出图片宽度({w})")
    if coord["y1"] < 0 or coord["y1"] >= h:
        warnings.append(f"y1={coord['y1']} 超出图片高度({h})")
    if coord["y2"] <= 0 or coord["y2"] > h:
        warnings.append(f"y2={coord['y2']} 超出图片高度({h})")

    coord_w = coord["x2"] - coord["x1"]
    coord_h = coord["y2"] - coord["y1"]
    if coord_w > w * 1.5:
        warnings.append(f"坐标宽度({coord_w})远超图片宽度({w})")
    if coord_h > h * 1.5:
        warnings.append(f"坐标高度({coord_h})远超图片高度({h})")

    if warnings:
        print(f"[坐标校验] {'; '.join(warnings)}")


# 题号匹配模式：检测文本中潜在的题目切换点
# 1. 阿拉伯数字序号（排除单位写法如 5N, 1kg, 10³）
_QUESTION_NUM_PATTERN = re.compile(
    r"(?<!\d)(\d+)[.、．]"
    r"(?!\s*[Nnkgm㎡³²%/hH])\s*"
    '["\u201c\u201d\u300c\u300e「『【\\(（]?'  # 允许可选的前引号/括号
    r"[\u4e00-\u9fffA-Za-z]"  # 中文或英文字母开头
)
# 2. 新题起始关键词：匹配新题引入
# "某"是中文应用题典型的题目起始词
_NEW_QUESTION_PATTERN = re.compile(
    r"(?:^|(?<=\s)|(?<=[。；！？!?\n]))\s*"
    r"(某[石块体积为]|有一?[块个段小]|质量为|体积为|求[该此]|质为|运输|\u201c借来)"  # 补充常见历史题起始词
    r"[\u4e00-\u9fff\da-zA-Z×÷]"
)
# 3. 选择题选项结束 → 新题切换：检测选项D/结尾后紧跟新句子
_ANSWER_TO_NEW_Q_PATTERN = re.compile(
    r"[Dd][.、．]?\s*[\u4e00-\u9fffA-Za-z].*?[。；！？!?？]\s*"
    r"(?!\s*(?:[A-Da-d][.、．]))"  # 不是下一个选项
    r"(?=[\u4e00-\u9fff]{2,})"  # 至少2个汉字开头 → 新题
)

def _split_merged_questions(text: str, coordinate: dict | None) -> list[dict]:
    """
    后处理：当 API 将多道题合并为一道时，按题号或新题关键词拆分
    返回每道题的 {"text", "coordinate"} 列表，coordinate 按文字长度比例拆分

    :param text: 合并的题目文本
    :param coordinate: 原始外接矩形坐标
    :return: 拆分后的题目列表
    """
    if not text or len(text) < 30:
        return [{"text": text, "coordinate": coordinate}]

    # 收集所有可能的切分点（字符位置）
    split_positions = set()

    for m in _QUESTION_NUM_PATTERN.finditer(text):
        split_positions.add(m.start())
    for m in _NEW_QUESTION_PATTERN.finditer(text):
        split_positions.add(m.start())
    for m in _ANSWER_TO_NEW_Q_PATTERN.finditer(text):
        split_positions.add(m.end())  # 选项结束后位置为切分点

    # 必须有多个切分点才执行拆分
    split_positions = sorted(split_positions)
    if len(split_positions) < 2:
        return [{"text": text, "coordinate": coordinate}]

    # 按位置切分文本
    segments = []
    prev = 0
    for pos in split_positions:
        if pos <= prev:
            continue
        seg_text = text[prev:pos].strip()
        if seg_text and len(seg_text) > 10:
            segments.append(seg_text)
        prev = pos
    # 最后一段
    remaining = text[prev:].strip()
    if remaining and len(remaining) > 5:
        segments.append(remaining)

    if len(segments) <= 1:
        return [{"text": text, "coordinate": coordinate}]

    # 合并过短片段（小于30字）到前一个片段中
    merged = []
    for seg in segments:
        if merged and len(seg) < 30:
            merged[-1] += seg
        else:
            merged.append(seg)

    if len(merged) <= 1:
        return [{"text": text, "coordinate": coordinate}]

    # 按长度比例分配坐标
    total_len = sum(len(s) for s in merged)
    result = []
    y_offset = 0
    y_range = (coordinate.get("y2", 0) - coordinate.get("y1", 0)) if coordinate else 0
    for seg in merged:
        seg_coord = None
        if coordinate and y_range > 0:
            ratio = len(seg) / total_len
            y_start = coordinate["y1"] + y_offset
            y_end = int(y_start + y_range * ratio)
            seg_coord = {
                "x1": coordinate["x1"],
                "y1": y_start,
                "x2": coordinate["x2"],
                "y2": y_end,
            }
            y_offset = y_end - coordinate["y1"]
        result.append({"text": seg, "coordinate": seg_coord})

    return result


class _OCRItemValidator(BaseModel):
    page_num: int = Field(ge=1)
    question_index: int = Field(ge=0)
    subject: str = Field(min_length=1, max_length=20)
    question_text: str | None = None
    question_image: str | None = None
    coordinate: dict | None = None
    full_score: float = Field(gt=0)


class OCRService:
    """OCR 数据校验与标准化"""

    @staticmethod
    def validate_ocr_data(ocr_data: list[dict]) -> list[dict]:
        if not ocr_data:
            raise ValueError("OCR 数据列表为空")

        validated = []
        for i, item in enumerate(ocr_data):
            try:
                v = _OCRItemValidator(**item)
            except ValidationError as e:
                logger.error("OCR 数据第 %d 项校验失败: %s", i, e)
                raise ValueError(f"OCR 数据第 {i} 项不合法: {e}")

            subject_map = {"数学": "math", "语文": "chinese", "英语": "english"}
            subject = v.subject.strip()
            subject = subject_map.get(subject, subject.lower())

            validated.append({
                "page_num": v.page_num,
                "question_index": v.question_index,
                "subject": subject,
                "question_text": v.question_text or "",
                "question_image": v.question_image,
                "coordinate": v.coordinate,
                "full_score": v.full_score,
            })

        return validated

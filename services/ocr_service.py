"""
OCR识别与切题服务模块
提供阿里云整页试卷识别和题目裁剪功能，通过Celery后台任务串联：读取清洗后图片 → OCR识别 → 切题 → 结果入库
同时根据切题坐标从清洗后图片裁剪出题目图片，保存到 data/cut_images/

日期： 2026/5/18

创建者：罗東明
"""
import json
import os
import re
import uuid

import cv2

from alibabacloud_ocr_api20210707.models import (
    RecognizeEduPaperOcrRequest,
    RecognizeEduPaperCutRequest,
    RecognizeEduPaperStructedRequest,
)
from sqlalchemy import select

from core.celery_app import celery_app
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from models.question_result import QuestionResult
from utils.aliyun_client import ocr_client

# 裁剪图片保存目录
CUT_DIR = "data/cut_images"


def page_recognize(
    body: bytes,
    image_type: str = "photo",
    subject: str = "default",
    output_oricoord: bool = False,
) -> dict:
    """
    整页试卷识别，调用阿里云 RecognizeEduPaperOcr 接口

    :param body: 图片二进制数据
    :param image_type: 图片类型，photo 或 scan
    :param subject: 学科标签
    :param output_oricoord: 是否输出原图坐标
    :return: 识别结果字典
    """
    request = RecognizeEduPaperOcrRequest(
        image_type=image_type,
        subject=subject,
        output_oricoord=output_oricoord,
    )
    request.body = body
    response = ocr_client.recognize_edu_paper_ocr(request)
    return json.loads(response.body.data)


def paper_cut(
    body: bytes,
    cut_type: str = "question",
    image_type: str = "photo",
    subject: str = "default",
    output_oricoord: bool = False,
) -> dict:
    """
    试卷切题，调用阿里云 RecognizeEduPaperCut 接口（旧版，保留作为备选）

    :param body: 图片二进制数据
    :param cut_type: 裁剪类型，默认 question
    :param image_type: 图片类型，photo 或 scan
    :param subject: 学科标签
    :param output_oricoord: 是否输出原图坐标
    :return: 切题结果字典
    """
    request = RecognizeEduPaperCutRequest(
        cut_type=cut_type,
        image_type=image_type,
        subject=subject,
        output_oricoord=output_oricoord,
    )
    request.body = body
    response = ocr_client.recognize_edu_paper_cut(request)
    return json.loads(response.body.data)


def paper_structed(
    body: bytes,
    subject: str = "default",
    need_rotate: bool = True,
    output_oricoord: bool = True,
) -> dict:
    """
    精细版结构化切题，调用阿里云 RecognizeEduPaperStructed 接口
    支持多学科教辅试卷的结构化识别，自动切题并识别文字内容和坐标位置
    内部自带图像增强（自动旋转、畸变矫正、模糊增强），无需预处理

    返回结构：data → {"part_info": [{"part_title": "选择题", "subject_list": [{"text": ..., "pos_list": ...}]}]}

    :param body: 图片二进制数据
    :param subject: 学科标签，如 Physics、JHighSchool_Physics 等
    :param need_rotate: 是否需要自动旋转功能
    :param output_oricoord: 是否输出原图坐标信息
    :return: 结构化切题结果字典
    """
    request = RecognizeEduPaperStructedRequest(
        subject=subject,
        need_rotate=need_rotate,
        output_oricoord=output_oricoord,
    )
    request.body = body
    response = ocr_client.recognize_edu_paper_structed(request)
    return json.loads(response.body.data)


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
    r"(?!\s*[Nnkgm㎡³²%/h])\s*"
    r"[\u4e00-\u9fff]"
)
# 2. 新题起始关键词：匹配新题引入
# "某"是中文应用题典型的题目起始词
_NEW_QUESTION_PATTERN = re.compile(
    r"(?:^|(?<=\s)|(?<=[。；！？!?\n]))\s*"
    r"(某[石块体积为]|有一?[块个段小]|质量为|体积为|求[该此]|质为)"
    r"[\u4e00-\u9fff\da-zA-Z×÷]"
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


def _sync_update_db_status(
    assignment_task_id: int,
    celery_task_id: str,
    status: int,
    error: str = None,
):
    """
    同步更新数据库中的作业任务状态和异步日志状态

    :param assignment_task_id: 作业主表记录ID
    :param celery_task_id: Celery 分配的任务UUID
    :param status: 状态码 (2=完成, 3=失败)
    :param error: 错误信息
    """
    with SyncSessionLocal() as db:
        assignment_task = db.get(AssignmentTask, assignment_task_id)
        if assignment_task:
            assignment_task.task_status = status
            if error:
                assignment_task.error_msg = error

        stmt = select(AsyncTask).where(AsyncTask.assignment_task_id == assignment_task_id)
        result = db.execute(stmt)
        async_log = result.scalars().first()
        if async_log:
            async_log.status = status
            async_log.celery_task_id = celery_task_id
            if error:
                async_log.error_detail = error
        else:
            new_log = AsyncTask(
                assignment_task_id=assignment_task_id,
                celery_task_id=celery_task_id,
                status=status,
                error_detail=error if error else None,
            )
            db.add(new_log)

        db.commit()


@celery_app.task(bind=True, name="process_ocr_task")
def process_ocr_task(
    self,
    assignment_task_id: int,
    processed_image_path: str = None,
    raw_image_path: str = None,
):
    """
    Celery 后台任务：对图片进行 OCR 识别 + 结构化切题，结果存入 question_results 表
    切题优先使用 RecognizeEduPaperStructed（精细版结构化切题，内置图像增强），
    如果 part_info 为空则回退 RecognizeEduPaperCut（旧版）进行重试
    同时根据坐标从 processed_image 裁剪出题目图片保存到 data/cut_images/

    :param self: Celery任务实例自身 (为了获取 request.id)
    :param assignment_task_id: 数据库中的作业任务ID
    :param processed_image_path: 清洗后图片的物理路径（用于OCR文字识别 + 裁剪源图）
    :param raw_image_path: 原始图片的物理路径（用于结构化切题，Structed 内置图像增强）
    """
    try:
        # 决定用哪张图做OCR识别：优先 processed，其次 raw
        ocr_image_path = processed_image_path if processed_image_path and os.path.exists(processed_image_path) else raw_image_path
        if not ocr_image_path or not os.path.exists(ocr_image_path):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"OCR识别的图片不存在 (processed={processed_image_path}, raw={raw_image_path})",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        # 结构化切题优先用原始图片（Structed 内置图像增强，无需预处理）
        cut_image_path = raw_image_path if raw_image_path and os.path.exists(raw_image_path) else ocr_image_path
        # 裁剪题目图片时优先用原始图片（坐标来自原始图片空间）
        crop_source_path = raw_image_path if raw_image_path and os.path.exists(raw_image_path) else processed_image_path

        # 步骤1：整页试卷识别（用 processed 图片获取 OCR 结果用于展示/验证）
        with open(ocr_image_path, "rb") as f:
            image_body = f.read()
        ocr_type = "scan" if ocr_image_path == processed_image_path else "photo"
        ocr_result = page_recognize(body=image_body, image_type=ocr_type)
        if not ocr_result or not ocr_result.get("content"):
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OCR整页识别返回空结果",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        # 额外对原始图片做 OCR 用于文本拆分（原始图片 OCR 质量通常更好）
        ocr_content_for_split = ocr_result.get("content", "")
        if cut_image_path != ocr_image_path and os.path.exists(cut_image_path):
            try:
                with open(cut_image_path, "rb") as f_raw:
                    raw_body = f_raw.read()
                raw_ocr_type = "photo"
                raw_ocr = page_recognize(body=raw_body, image_type=raw_ocr_type)
                if raw_ocr and raw_ocr.get("content"):
                    raw_text = raw_ocr["content"]
                    if len(raw_text) > len(ocr_content_for_split):
                        ocr_content_for_split = raw_text
            except Exception:
                pass

        # 步骤2：结构化切题（主方案）
        # 使用 RecognizeEduPaperStructed，内置图像增强，无需指定 image_type
        with open(cut_image_path, "rb") as f:
            cut_body = f.read()

        cut_result = None
        used_api = None

        # 2a. 先尝试 Structed（精细版结构化切题）
        try:
            structed_result = paper_structed(body=cut_body, subject="default", need_rotate=True, output_oricoord=True)
            if structed_result and structed_result.get("part_info"):
                # 检查是否有实际的题目内容
                has_subjects = any(
                    len(p.get("subject_list", [])) > 0
                    for p in structed_result["part_info"]
                )
                if has_subjects:
                    cut_result = structed_result
                    used_api = "RecognizeEduPaperStructed"
                    print("结构化切题成功：RecognizeEduPaperStructed")
        except Exception as e:
            print(f"RecognizeEduPaperStructed 失败，准备回退: {e}")

        # 2b. 回退方案：用旧版 paper_cut 重试
        if cut_result is None:
            for try_img_type in ["photo", "scan"]:
                try:
                    cut_result = paper_cut(body=cut_body, image_type=try_img_type, output_oricoord=True)
                    if cut_result:
                        page_list = cut_result.get("page_list", [])
                        has_subjects = any(
                            len(p.get("subject_list", [])) > 0 for p in page_list
                        )
                        if has_subjects:
                            used_api = f"RecognizeEduPaperCut({try_img_type})"
                            break
                except Exception as e:
                    print(f"paper_cut({try_img_type}) 失败: {e}")

        if cut_result is None:
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="所有切题方案均返回空结果",
            )
            return {"status": "failed", "task_id": assignment_task_id}

        print(f"切题成功：{used_api}")

        # 步骤3：将切题结果写入 question_results 表，同时裁剪题目图片
        os.makedirs(CUT_DIR, exist_ok=True)
        with SyncSessionLocal() as db:
            saved_count = _save_question_results(
                db, assignment_task_id, cut_result,
                crop_source_path=crop_source_path,
                ocr_content=ocr_content_for_split,
            )

        # 更新任务状态为完成
        _sync_update_db_status(
            assignment_task_id,
            self.request.id,
            status=2,
        )

        return {
            "status": "success",
            "task_id": assignment_task_id,
            "questions_saved": saved_count,
        }

    except Exception as e:
        try:
            _sync_update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"OCR处理发生异常: {str(e)}",
            )
        except Exception as inner_e:
            print(f"更新数据库状态失败: {inner_e}")
        raise e

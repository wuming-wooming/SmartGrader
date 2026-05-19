"""
图像处理服务模块
提供图片的本地清洗、去黑边、文字增强等功能, 该模块的方法将被 Celery Worker 在后台进程中执行

日期： 2026/5/15

创建者：周康哲
"""

import os
import cv2


# 对输入图片进行 OpenCV 清洗处理, 并保存到输出路径
def _do_opencv_cleaning(input_path: str, output_path: str) -> bool:
    """
    对输入图片进行 OpenCV 清洗处理, 并保存到输出路径
    处理流程：灰度化 -> 阈值二值化找轮廓 -> 裁剪黑边 -> 自适应阈值增强文字

    :param input_path: 输入图片路径
    :param output_path: 输出图片路径
    :return: 如果处理成功则返回 True, 否则返回 False
    """
    if not os.path.exists(input_path):
        return False
    img = cv2.imread(input_path)
    if img is None:
        return False

    # 灰度化（先将彩色的原图转换为灰度图，亮度值0-255）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 自适应阈值二值化找出所有深色内容（文字、线条）
    # blockSize=51(C=10)：较大的窗口确保即使是较粗的笔画也能被完整识别，不会变成空心轮廓
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 10
    )

    # 膨胀操作：使用较大的核，强制将相近的文字段落、题目连通成大块区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    dilated = cv2.dilate(binary, kernel, iterations=2)

    # 查找所有连通区域
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        img_h, img_w = gray.shape
        img_area = img_w * img_h
        valid_contours = []

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # 使用外接矩形面积过滤：
            # 1. 过滤掉过小的噪点 (> 0.0005)
            # 2. 过滤掉图像边缘/整图边框的伪轮廓 (< 0.90)
            if w * h > img_area * 0.0005 and w * h < img_area * 0.90:
                valid_contours.append(c)

        if valid_contours:
            x_min = min([cv2.boundingRect(c)[0] for c in valid_contours])
            y_min = min([cv2.boundingRect(c)[1] for c in valid_contours])
            x_max = max(
                [
                    cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2]
                    for c in valid_contours
                ]
            )
            y_max = max(
                [
                    cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3]
                    for c in valid_contours
                ]
            )

            w = x_max - x_min
            h = y_max - y_min

            if w * h > img_area * 0.05 and w * h < img_area * 0.99:
                pad = 40
                pad_y = 60
                x1 = max(0, x_min - pad)
                y1 = max(0, y_min - pad_y)
                x2 = min(img_w, x_max + pad)
                y2 = min(img_h, y_max + pad_y)
                gray = gray[y1:y2, x1:x2]

    # 2. 自适应阈值增强文字 (修正为 THRESH_BINARY 保持白底黑字)
    enhanced = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 10
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, enhanced)
    return True

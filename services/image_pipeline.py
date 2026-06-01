"""
可配置的图像预处理管道
将图像处理流程拆分为独立的 PipelineStep，支持按环境变量 IMAGE_PIPELINE_STEPS 组合

日期： 2026/5/22
"""
import os
from abc import ABC, abstractmethod

import cv2
import numpy as np

from core import config


class PipelineStep(ABC):
    """图像处理管道步骤基类"""

    def __init__(self, name: str, enabled: bool = True, **kwargs):
        self.name = name
        self.enabled = enabled
        self.kwargs = kwargs

    @abstractmethod
    def process(self, image: np.ndarray) -> np.ndarray:
        """处理图像，返回处理后的图像"""


# ======================== 具体步骤 ========================


class GrayscaleStep(PipelineStep):
    """灰度化"""

    def process(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image


class ThresholdStep(PipelineStep):
    """自适应阈值二值化（用于找出深色内容区域）"""

    def process(self, image: np.ndarray) -> np.ndarray:
        block_size = int(self.kwargs.get("block_size", 51))
        c_val = int(self.kwargs.get("c", 10))
        # 确保 block_size 为奇数
        if block_size % 2 == 0:
            block_size += 1
        return cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block_size, c_val,
        )


class DenoiseStep(PipelineStep):
    """降噪"""

    def process(self, image: np.ndarray) -> np.ndarray:
        method = self.kwargs.get("method", "bilateral")
        if method == "gaussian":
            ksize = int(self.kwargs.get("ksize", 3))
            if ksize % 2 == 0:
                ksize += 1
            return cv2.GaussianBlur(image, (ksize, ksize), 0)
        elif method == "median":
            ksize = int(self.kwargs.get("ksize", 3))
            if ksize % 2 == 0:
                ksize += 1
            return cv2.medianBlur(image, ksize)
        elif method == "nlm":
            return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
        elif method == "bilateral":
            d = int(self.kwargs.get("d", 9))
            sigma_color = int(self.kwargs.get("sigma_color", 75))
            sigma_space = int(self.kwargs.get("sigma_space", 75))
            return cv2.bilateralFilter(image, d, sigma_color, sigma_space)
        return image


class CropStep(PipelineStep):
    """去黑边/空白边：通过轮廓检测找到内容区域，裁剪边界"""

    def process(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 如果输入不是二值图，先做一次自适应阈值
        block_size = int(self.kwargs.get("crop_block_size", 51))
        if block_size % 2 == 0:
            block_size += 1
        c_val = int(self.kwargs.get("crop_c", 10))
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block_size, c_val,
        )

        # 膨胀连通
        kernel_size = int(self.kwargs.get("dilation_kernel", 20))
        iterations = int(self.kwargs.get("dilation_iterations", 2))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        dilated = cv2.dilate(binary, kernel, iterations=iterations)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image

        h, w = gray.shape[:2]
        img_area = w * h
        min_area_ratio = float(self.kwargs.get("min_area_ratio", 0.01))
        max_area_ratio = float(self.kwargs.get("max_area_ratio", 0.98))
        min_content_ratio = float(self.kwargs.get("min_content_ratio", 0.05))
        max_content_ratio = float(self.kwargs.get("max_content_ratio", 0.99))
        pad = int(self.kwargs.get("padding", 20))
        pad_y = int(self.kwargs.get("padding_y", 20))

        valid = []
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if img_area * min_area_ratio < area < img_area * max_area_ratio:
                valid.append(c)

        if not valid:
            return image

        x_min = min(cv2.boundingRect(c)[0] for c in valid)
        y_min = min(cv2.boundingRect(c)[1] for c in valid)
        x_max = max(cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2] for c in valid)
        y_max = max(cv2.boundingRect(c)[1] + cv2.boundingRect(c)[3] for c in valid)

        content_w = x_max - x_min
        content_h = y_max - y_min
        if img_area * min_content_ratio < content_w * content_h < img_area * max_content_ratio:
            x1 = max(0, x_min - pad)
            y1 = max(0, y_min - pad_y)
            x2 = min(w, x_max + pad)
            y2 = min(h, y_max + pad_y)
            return image[y1:y2, x1:x2]

        return image


class EnhanceStep(PipelineStep):
    """文字增强"""

    def process(self, image: np.ndarray) -> np.ndarray:
        method = self.kwargs.get("method", "morphology")
        if method == "adaptive_threshold":
            block_size = int(self.kwargs.get("block_size", 21))
            if block_size % 2 == 0:
                block_size += 1
            c_val = int(self.kwargs.get("c", 10))
            return cv2.adaptiveThreshold(
                image, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY, block_size, c_val,
            )
        elif method == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)
        elif method == "sharpen":
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            return cv2.filter2D(image, -1, kernel)
        elif method == "morphology":
            kernal = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            dilated = cv2.dilate(image, kernal, iterations=1)
            eroded = cv2.erode(dilated, kernal, iterations=1)
            return eroded
        return image


class DeskewStep(PipelineStep):
    """倾斜校正：基于霍夫变换检测文本行角度，校正图像"""

    def process(self, image: np.ndarray) -> np.ndarray:
        # 确保输入为灰度图
        gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        # 霍夫变换检测直线（文本行）
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        if lines is None:
            return image

        # 计算所有直线的角度，取中位数
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle = (theta * 180 / np.pi) - 90
            if abs(angle) < 45:  # 过滤极端角度
                angles.append(angle)

        if not angles:
            return image

        median_angle = np.median(angles)
        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        # 旋转校正
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        corrected = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return corrected


class LightEqualizeStep(PipelineStep):
    """光照均衡：解决局部明暗不均，提升文字与背景对比度"""

    def process(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            # 转换到YCrCb色彩空间（分离亮度通道）
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y_channel, cr, cb = cv2.split(ycrcb)
        else:
            y_channel = image.copy()

        # 自适应直方图均衡（CLAHE）优化亮度
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16, 16))  # 调大tile适配作业纸张
        equalized_y = clahe.apply(y_channel)

        if len(image.shape) == 3:
            equalized_ycrcb = cv2.merge([equalized_y, cr, cb])
            return cv2.cvtColor(equalized_ycrcb, cv2.COLOR_YCrCb2BGR)
        return equalized_y


class BackgroundRemoveStep(PipelineStep):
    """背景去除：保留文字前景，消除杂色背景干扰"""

    def process(self, image: np.ndarray) -> np.ndarray:
        gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 大津二值化（自动阈值，适配不同亮度的作业纸）
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # 形态学开运算（先腐蚀后膨胀）去除小噪点
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary_clean = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        # 生成背景掩码：文字区域保留原图，背景填充白色
        mask = cv2.bitwise_not(binary_clean)
        result = np.where(mask == 255, 255, gray)
        return result


# ======================== 管道 ========================


class ImagePipeline:
    """可配置的图像处理管道"""

    STEP_MAP = {
        "grayscale": GrayscaleStep, # 灰度化
        "threshold": ThresholdStep, # 二值化
        "denoise": DenoiseStep, # 降噪
        "crop": CropStep, # 去黑边
        "enhance": EnhanceStep, # 文字增强
        "deskew": DeskewStep, # 倾斜校正
        "light_equalize": LightEqualizeStep, # 光照均衡
        "background_remove": BackgroundRemoveStep, # 背景去除
    }

    def __init__(self, steps: list[PipelineStep]):
        self._steps = steps

    @classmethod
    def from_config(cls, steps_str: str | None = None) -> "ImagePipeline":
        """从配置字符串构建管道，如 "grayscale(enabled=True),denoise(method=bilateral,d=9),crop(padding=2e)" """
        if steps_str is None:
            steps_str = config.IMAGE_PIPELINE_STEPS
        print(f"[ImagePipeline] Using pipeline: {steps_str}")
        step_names = [s.strip() for s in steps_str.split(",") if s.strip()]
        steps = []
        for step_part in steps_str.split(","):
            if not step_part.strip():
                continue
            if "(" in step_part:
                name, params_str = step_part.split("(", 1)
                name = name.strip()
                params_str = params_str.strip().rstrip(")")
                # 解析参数
                kwargs = {}
                for param in params_str.split(","):
                    if "=" in param:
                        k, v = param.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        # 类型转换
                        if v.isdigit():
                            kwargs[k] = int(v)
                        elif v.replace(".", "").isdigit():
                            kwargs[k] = float(v)
                        elif v.lower() in ["true", "false"]:
                            kwargs[k] = v.lower() == "true"
                        else:
                            kwargs[k] = v
            else:
                name = step_part.strip()
                kwargs = {}
            # 创建步骤实例
            cls_type = cls.STEP_MAP.get(name)
            if cls_type:
                steps.append(cls_type(name=name, **kwargs))
        return cls(steps)

    def run(self, input_path: str, output_path: str) -> bool:
        """执行管道处理，保存到 output_path"""
        if not os.path.exists(input_path):
            return False
        img = cv2.imread(input_path)
        if img is None:
            return False

        for step in self._steps:
            if step.enabled:
                img = step.process(img)

        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if not output_path.endswith(".png"):
            output_path = os.path.splitext(output_path)[0] + ".png"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, img, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        return True

    @property
    def step_names(self) -> list[str]:
        return [s.name for s in self._steps if s.enabled]

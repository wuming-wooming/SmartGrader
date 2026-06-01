"""
图像处理服务模块
提供图片的本地清洗、去黑边、文字增强等功能, 该模块的方法将被 Celery Worker 在后台进程中执行

日期： 2026/5/15

创建者：周康哲
"""

import os

from services.image_pipeline import ImagePipeline

# 管道单例
_pipeline: ImagePipeline | None = None


def _get_pipeline() -> ImagePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ImagePipeline.from_config()
    return _pipeline


# 对输入图片进行 OpenCV 清洗处理, 并保存到输出路径
def _do_opencv_cleaning(input_path: str, output_path: str) -> bool:
    """
    对输入图片进行管道化清洗处理, 并保存到输出路径
    默认管道：grayscale → threshold → crop → enhance
    可通过 IMAGE_PIPELINE_STEPS 环境变量配置

    :param input_path: 输入图片路径
    :param output_path: 输出图片路径
    :return: 如果处理成功则返回 True, 否则返回 False
    """
    pipeline = _get_pipeline()
    if not os.path.exists(input_path):
        return False
    return pipeline.run(input_path, output_path)

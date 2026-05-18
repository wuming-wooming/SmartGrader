"""
阿里云 OCR SDK 客户端单例模块
封装 Aliyun OcrClient 的创建与复用，统一从全局配置读取 AK/SK/Endpoint

日期： 2026/5/18

创建者：罗東明
"""

from alibabacloud_ocr_api20210707.client import Client as OcrClient
from alibabacloud_tea_openapi import models as open_api_models

from core import config


def _create_ocr_client() -> OcrClient:
    """
    创建并返回一个阿里云 OCR 客户端实例
    从 core.config 读取 AccessKeyId、AccessKeySecret、Endpoint

    :return: 阿里云 OCR 客户端实例
    """
    aliyun_config = open_api_models.Config(
        access_key_id=config.ALIBABA_CLOUD_ACCESS_KEY_ID,
        access_key_secret=config.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
        endpoint=config.ALIBABA_CLOUD_ENDPOINT,
    )
    return OcrClient(aliyun_config)


# 全局单例 —— 模块导入时只初始化一次
ocr_client = _create_ocr_client()

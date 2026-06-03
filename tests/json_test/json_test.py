import json
import os

import requests

from core.database import SyncSessionLocal
from services.baidu_homework_grading import BaiduHomeworkGradingAPI
from services.ocr_engine import BaiduOCREngine
from tasks.baidu_homework_tasks import _backfill_baidu_grading, _sync_update_db_status

# if __name__ == "__main__":
#     ret = BaiduHomeworkGradingAPI().poll_result("2056732762435370599")
#     print(ret)
#     # 写入
#     json.dump(ret, open("result2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # ret = json.load(open("result2.json", encoding="utf-8"))
    # questions = BaiduHomeworkGradingAPI().parse_grading_result(ret)
    # print(questions)
    with open("6.jpg", "rb") as img:
        print(BaiduOCREngine._encode_image(img.read())[:100] + "_____")
        print(BaiduOCREngine._encode_image(img.read(), urlencoded=True)[:100] + "_____")

# if __name__ == "__main__":
#     url = "http://tv-mis.bj.bcebos.com//correct_evaluate_data/24b25f3e0217ed05722c63c20b0e4aaf02/2056732762435370599/24b25f3e0217ed05722c63c20b0e4aaf02/cdfce94e-352a-45f1-8812-57f02911b8bf.png?authorization=bce-auth-v1%2FALTAK5AGAcpDzr9LsTXvf4PbuU%2F2026-05-19T13%3A44%3A44Z%2F86400%2Fhost%2Fdac02449241eaaf13a3d0255b8a10ba91611506f63e0be08fa2bbb5bef42494f"
#     ret = requests.get(url) # 获取的是图片（.png）
#     ret = ret.content
#     # 写入本地文件，保存图片
#     with open("test.png", "wb") as f:
#         f.write(ret)
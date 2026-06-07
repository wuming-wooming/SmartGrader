import json
import os

import requests

from core.database import SyncSessionLocal
from services.baidu_homework_grading import BaiduHomeworkGradingAPI
from services.ocr_engine import BaiduOCREngine
import json
from tasks.baidu_homework_tasks import _backfill_baidu_grading, _sync_update_db_status

# if __name__ == "__main__":
#     ret = BaiduHomeworkGradingAPI().poll_result("2056732762435370599")
#     print(ret)
#     # 写入
#     json.dump(ret, open("result2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


# if __name__ == "__main__":
#     # ret = json.load(open("result2.json", encoding="utf-8"))
#     # questions = BaiduHomeworkGradingAPI().parse_grading_result(ret)
#     # print(questions)
#     with open("6.jpg", "rb") as img:
#         print(BaiduOCREngine._encode_image(img.read())[:100] + "_____")
#         print(BaiduOCREngine._encode_image(img.read(), urlencoded=True)[:100] + "_____")

# if __name__ == "__main__":
#     url = "http://tv-mis.bj.bcebos.com//correct_evaluate_data/24b25f3e0217ed05722c63c20b0e4aaf02/2056732762435370599/24b25f3e0217ed05722c63c20b0e4aaf02/cdfce94e-352a-45f1-8812-57f02911b8bf.png?authorization=bce-auth-v1%2FALTAK5AGAcpDzr9LsTXvf4PbuU%2F2026-05-19T13%3A44%3A44Z%2F86400%2Fhost%2Fdac02449241eaaf13a3d0255b8a10ba91611506f63e0be08fa2bbb5bef42494f"
#     ret = requests.get(url) # 获取的是图片（.png）
#     ret = ret.content
#     # 写入本地文件，保存图片
#     with open("test.png", "wb") as f:
#         f.write(ret)

if __name__ == "__main__":
    # # 普通文本
    # text1 = """{
    # "is_correct": 1,
    # "score": 1.0,
    # "error_reason": "",
    # "correct_answer": "1.0",
    # "comment": "1234,test,test,TEST"
    # }"""
    # # 带换行等特殊字符
    # test2 = """{
    # "is_correct": 0,
    # "score": 0.0,
    # "error_reason": "答案错误",
    # "correct_answer": "1.0",
    # "comment": "1234,test,test,TEST   \n\n \t"
    # }"""
    # # 带LaTeX格式
    # test3 = """{
    # "is_correct": 0,
    # "score": 0.0,
    # "error_reason": "答案错误",
    # "correct_answer": "1.0",
    # "comment": "1234,test,test,TEST   \n\n \t"
    # "LaTex": "\int \frac{1}{\sqrt{1-x^{2}}}\mathrm{d}x= \arcsin x +C "
    # }"""
    # # 处理后的LaTex
    # text4 = """{
    # "is_correct": 0,
    # "score": 0.0,
    # "error_reason": "答案错误",
    # "correct_answer": "1.0",
    # "comment": "1234,test,test,TEST   \n\n \t"
    # "LaTex": "\\int \\frac{1}{\\sqrt{1-x^{2}}}\\mathrm{d}x= \\arcsin x +C "
    # }"""

    text5 = """{
    "is_correct": 1,
    "score": 10.0,
    "error_reason": "",
    "correct_answer": "A 12 + 3 = \n 15",
    "comment": "同学做得非常棒！你对最简二次根式的两个判定条件掌握得很扎实：一是被开方数不含分母，二是被开方数中不含能开得尽方的因数或因式。能够准确识别出 $\sqrt{5}$ 和 $\sqrt{x^2+y^2}$ 是最简二次根式，而排除了含有分母或能开方的项。继续保持这种严谨的解题习惯！"
}"""
    text6 = """{'is_correct': 0, 'score': 0.0, 'error_reason': '学生忽略了分母不能为零的限制条件。要使等式成立，需满足被开方数非负且分母不为零，即 2-x≥0 且 x+1>0，解得 -1<x≤2。学生误选了C，包含了x=-1的情况，此时分母为0无意义。', 'correct_answer': 'D', 'comment': '同学你好！这道题考察的是二次根式的除法法则及其成立条件。你注意到了被开方数必须非负（2-x≥0），这点很棒！但是要注意，根号下的式子如果在分母上，它不仅要是非负数，更不能等于0（因为0不能做除数）。所以 x+1 必须严格大于 0。下次做题时记得给分母加个“紧箍咒”哦，继续加油！'}"""

    # o1 = json.loads(text1)
    # o2 = json.loads(test2)
    # o3 = json.loads(test3)
    # o4 = json.loads(text4)
    # i = 1

    from services.llm.output_parser import parse_grading_result
    # parse_grading_result(text6, 10)
    a = parse_grading_result(text5, 10)
    print(a)
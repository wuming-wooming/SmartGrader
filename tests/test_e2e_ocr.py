"""端到端测试：上传图片 → 清洗 → OCR识别+切题 → 验证结果"""
# 日期： 2026/5/18
# 创建者：罗東明

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from core.database import SyncSessionLocal
from models.question_result import QuestionResult
from models.assignment_task import AssignmentTask
from sqlalchemy import select

BASE = 'http://127.0.0.1:8001'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0IiwidXNlcm5hbWUiOiJ0ZXN0X2RlYnVnIiwiZXhwIjoxNzc5MTEyNjIzfQ.P7ygPq7dov_V6ExHXse0o4XhRu7__8idvAwrv69fh0k'

img_path = r'c:\Users\ark13\PycharmProjects\FastAPIProject3\res\ima\1 (1).jpg'

print(f'图片: {img_path} ({os.path.getsize(img_path)} bytes)')

# 1. 上传
with open(img_path, 'rb') as f:
    r = requests.post(
        f'{BASE}/images/upload_and_clean',
        headers={'Authorization': f'Bearer {TOKEN}'},
        files={'file': ('test.jpg', f, 'image/jpeg')}
    )
data = r.json()
task_id = data['task_id']
print(f'上传成功, task_id={task_id}')

# 2. 等待 Celery 处理
print('等待清洗+OCR自动处理(20秒)...')
time.sleep(20)

# 3. 验证结果
with SyncSessionLocal() as db:
    t = db.get(AssignmentTask, task_id)
    print(f'任务状态: {t.task_status}, 错误: {t.error_msg}')
    print(f'原始图片: {t.original_file}')
    print(f'清洗后: {t.processed_file}')

    qs = db.execute(
        select(QuestionResult).where(QuestionResult.task_id == task_id)
    ).scalars().all()
    print(f'\n识别题目数: {len(qs)}')
    for q in qs:
        txt = (q.question_text or 'N/A')[:120]
        print(f'  [{q.question_index}] {txt}')
        print(f'    坐标: {q.coordinate}')
        print(f'    学科: {q.subject}')
        print(f'    裁剪图片: {q.question_image}')
        if q.question_image and os.path.exists(q.question_image):
            size = os.path.getsize(q.question_image)
            print(f'    裁剪图片大小: {size} bytes')
        else:
            print(f'    裁剪图片: 未生成或不存在')

print('\n端到端测试完成!')

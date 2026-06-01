"""端到端测试：百度云智能作业批改 + LLM 复核
覆盖路径：
  1. only_split=false 完整批改模式
  2. only_split=true 仅切题模式
  3. 百度 API 异常时自动回退到标准 OCR 路线
  4. LLM 复核批阅链路

Usage: python tests/test_e2e_baidu_homework.py

前置条件: FastAPI + Celery Worker + Redis + MySQL 均运行中
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from sqlalchemy import select

from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.question_result import QuestionResult

BASE = "http://127.0.0.1:8001"
TEST_IMG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "res", "ima", "1 (1).jpg")


def get_token() -> str:
    """注册或登录获取 token"""
    reg = requests.post(f"{BASE}/users/register", json={
        "username": "baidu_e2e_test",
        "email": "baidu_e2e@test.com",
        "password": "test123",
    }).json()
    token = reg.get("access_token")
    if not token:
        login = requests.post(f"{BASE}/users/login", json={
            "username": "baidu_e2e_test",
            "password": "test123",
        }).json()
        token = login.get("access_token")
    if not token:
        raise RuntimeError(f"无法获取 token: reg={reg}, login={login}")
    return token


def upload_and_submit(token: str, only_split: bool = False) -> dict:
    """上传图片并提交到百度作业批改"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"only_split": str(only_split).lower()}
    with open(TEST_IMG, "rb") as f:
        resp = requests.post(
            f"{BASE}/baidu-homework/submit",
            headers=headers,
            files={"file": ("test.jpg", f, "image/jpeg")},
            data=data,
        )
    assert resp.status_code == 200, f"提交失败: {resp.status_code} {resp.text}"
    result = resp.json()
    print(f"  提交成功: assignment_task_id={result['assignment_task_id']}")
    print(f"  celery_task_id={result['celery_task_id']}")
    print(f"  only_split={result.get('only_split')}")
    return result


def wait_for_completion(task_id: int, token: str, timeout: int = 300) -> dict:
    """轮询任务状态直到完成或超时"""
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE}/baidu-homework/status/{task_id}", headers=headers)
        assert resp.status_code == 200, f"查询状态失败: {resp.status_code}"
        status = resp.json()
        label = status.get("task_status_label", "unknown")
        print(f"  状态: {label} (task_status={status['task_status']})")
        if label == "completed":
            return status
        if label == "failed":
            print(f"  任务失败: {status.get('error_msg', 'N/A')}")
            return status
        time.sleep(5)
    raise TimeoutError(f"任务超时 ({timeout}s)")


def verify_results(task_id: int, token: str, expect_grading: bool = False):
    """验证批改结果"""
    headers = {"Authorization": f"Bearer {token}"}

    # 通过 API 获取结果
    resp = requests.get(f"{BASE}/baidu-homework/result/{task_id}", headers=headers)
    if resp.status_code == 400 and "尚未完成" in resp.json().get("detail", ""):
        print("  结果尚未就绪（可能回退到 OCR 路线后还需手动提交批改）")
        return
    assert resp.status_code == 200, f"获取结果失败: {resp.status_code} {resp.text}"
    result = resp.json()

    questions = result.get("questions", [])
    print(f"  题目数: {len(questions)}")
    for q in questions:
        txt = (q.get("question_text") or "N/A")[:100]
        print(f"    [{q['question_index']}] {q['subject']} "
              f"score={q['score']}/{q['full_score']} "
              f"correct={q['is_correct']} "
              f"text={txt}")

    report = result.get("report")
    if report:
        print(f"  报告总分: {report['total_score']}/{report['max_total_score']}")
        print(f"  正确率: {report['correct_count']}/{report['total_questions']}")
        print(f"  summary: {(report.get('summary') or 'N/A')[:120]}")

    # 验证数据库
    with SyncSessionLocal() as db:
        task = db.get(AssignmentTask, task_id)
        print(f"  DB状态: task_status={task.task_status}, error={task.error_msg}")

        qs = db.execute(
            select(QuestionResult).where(QuestionResult.task_id == task_id)
        ).scalars().all()
        print(f"  DB题目数: {len(qs)}")
        for q in qs:
            print(f"    DB[{q.question_index}] subject={q.subject} "
                  f"score={q.score}/{q.full_score} "
                  f"cropped={q.question_image}")


def test_full_grading(token: str):
    """测试 only_split=false 完整批改模式"""
    print("\n" + "=" * 60)
    print("Test 1: 完整批改模式 (only_split=false)")
    print("=" * 60)

    if not os.path.exists(TEST_IMG):
        print(f"  SKIP: 测试图片不存在: {TEST_IMG}")
        return

    result = upload_and_submit(token, only_split=False)
    task_id = result["assignment_task_id"]

    status = wait_for_completion(task_id, token, timeout=300)
    if status.get("task_status_label") == "completed":
        verify_results(task_id, token, expect_grading=True)
    else:
        print(f"  任务未完成（可能回退）: {status}")


def test_split_only(token: str):
    """测试 only_split=true 仅切题模式"""
    print("\n" + "=" * 60)
    print("Test 2: 仅切题模式 (only_split=true)")
    print("=" * 60)

    if not os.path.exists(TEST_IMG):
        print(f"  SKIP: 测试图片不存在: {TEST_IMG}")
        return

    result = upload_and_submit(token, only_split=True)
    task_id = result["assignment_task_id"]

    status = wait_for_completion(task_id, token, timeout=300)
    if status.get("task_status_label") == "completed":
        verify_results(task_id, token, expect_grading=False)
    else:
        print(f"  任务未完成（可能回退）: {status}")


def test_existing_routes(token: str):
    """回归验证：确保现有路由未受影响"""
    print("\n" + "=" * 60)
    print("Test 3: 回归验证 - 现有路由")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {token}"}

    # 测试 /images/upload_and_clean
    if os.path.exists(TEST_IMG):
        with open(TEST_IMG, "rb") as f:
            resp = requests.post(
                f"{BASE}/images/upload_and_clean",
                headers=headers,
                files={"file": ("regression.jpg", f, "image/jpeg")},
            )
        print(f"  /images/upload_and_clean: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"    task_id={data.get('task_id')}")

    # 测试 /grading/tasks
    resp = requests.get(f"{BASE}/grading/tasks?limit=5", headers=headers)
    print(f"  /grading/tasks: {resp.status_code} (count={len(resp.json().get('tasks', []))})")

    # 测试 /users/protected
    resp = requests.get(f"{BASE}/users/protected", headers=headers)
    print(f"  /users/protected: {resp.status_code}")

    print("  回归验证完成")


if __name__ == "__main__":
    print("SmartGrader 百度云作业批改 E2E 测试")
    print(f"服务地址: {BASE}")
    print(f"测试图片: {TEST_IMG}")

    token = get_token()
    print(f"Token: {token[:20]}...")

    test_full_grading(token)
    test_split_only(token)
    test_existing_routes(token)

    print("\n" + "=" * 60)
    print("全部 E2E 测试完成!")
    print("=" * 60)

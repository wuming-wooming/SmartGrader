# SmartGrader API 文档

## 概述

- **Base URL**: `http://127.0.0.1:8001`
- **认证方式**: JWT Bearer Token（由 `/users/register` 或 `/users/login` 获取）
- **Swagger UI**: `http://127.0.0.1:8001/docs`
- **Content-Type**: `application/json`（文件上传使用 `multipart/form-data`）

## 认证说明

除 `/users/register` 和 `/users/login` 外，所有接口都需要在请求头中携带 JWT：

```
Authorization: Bearer <access_token>
```

Token 有效期为 30 分钟。过期后需重新登录获取新 Token。

## 状态码说明

| task_status | 含义 | 说明 |
|-------------|------|------|
| 0 | pending | 任务已创建，等待处理 |
| 1 | processing | 后台正在处理中 |
| 2 | completed | 处理完成 |
| 3 | failed | 处理失败（见 error_msg） |

async_task 的 status 字段使用相同编码。

---

## 完整业务流程

### 流程 1：图片上传 → 自动清洗 → OCR 识题

```
POST /images/upload_and_clean     # 上传图片，立即返回 task_id
    │                              # 后台自动执行：
    ├─ [Celery] OpenCV 清洗        #   去黑边、增强文字
    └─ [Celery] OCR + 切题         #   阿里云识别 + 结构化切题 → question_results 表
                                   # 切题结果可直接用于 /grading/submit
```

调用方只需上传图片，后续清洗和 OCR 自动串联完成。可通过轮询任务状态确认进度。

### 流程 2：提交 OCR 数据 → LLM 批改 → 报告生成

```
POST /grading/submit              # 提交 OCR 数据（questions[]），立即返回 task_id
    │                              # 后台自动执行：
    ├─ [Celery Chord] 并行评分     #   N 道题目同时调用 LLM 批改
    └─ [Celery Chord] 生成报告     #   聚合结果，调用 LLM 生成综合报告
                                   #
GET /grading/status/{task_id}      # 轮询任务状态
GET /grading/result/{task_id}      # 获取批改结果 + 报告（需 task_status=2）
```

---

## 接口详细说明

### 用户认证

#### POST `/users/register` — 用户注册

注册成功后自动返回 JWT Token，无需单独登录。

**请求体**:
```json
{
  "username": "student1",
  "email": "student1@school.edu",
  "password": "mysecret"
}
```

**响应** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**错误**:
- `400` — 用户名已被注册 / 邮箱已被注册

---

#### POST `/users/login` — 用户登录

**请求体**:
```json
{
  "username": "student1",
  "password": "mysecret"
}
```

**响应** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**错误**:
- `401` — 用户名或密码错误

---

#### GET `/users/protected` — 认证测试端点

**请求头**: `Authorization: Bearer <token>`

**响应** (200):
```json
{
  "message": "Hello student1, 您已通过JWT验证！"
}
```

---

### 图片处理

#### POST `/images/upload_and_clean` — 上传并触发图片清洗+OCR

这是图片处理链的**唯一入口**。上传图片后，后台自动完成清洗和 OCR 识题，无需手动调用 `/ocr/process`。

**请求**: `multipart/form-data`
| 参数 | 类型 | 说明 |
|------|------|------|
| `file` | file | 图片文件（仅限 image/* 类型） |

**响应** (200):
```json
{
  "task_id": 42,
  "message": "图片已成功上传，后台正在排队清洗中...",
  "raw_image_url": "data/raw_images/a1b2c3d4.jpg",
  "processed_image_url": null,
  "task_status": 0
}
```

**后续步骤**:
1. 记录返回的 `task_id`
2. 轮询 `GET /grading/status/{task_id}` 等待 `task_status` 变为 `2`（完成）
3. 处理完成后的切题结果可通过 `QuestionResultRepository` 查询，或用于 `/grading/submit`

**错误**:
- `400` — 文件类型不是图片
- `500` — 文件保存失败或数据库写入失败

---

### OCR 处理

#### POST `/ocr/process` — 手动触发 OCR 识别与切题

**注意**: 通常情况下不需要手动调用此接口。图片上传后会自动触发 OCR。此接口仅用于重试场景。

**请求**: Query 参数
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | int | 作业任务 ID（来自 `/images/upload_and_clean` 返回的 task_id） |

**响应** (200):
```json
{
  "status": "submitted",
  "task_id": 42,
  "questions_saved": 0,
  "message": "OCR任务已提交到后台处理"
}
```

---

### 批改管理

#### POST `/grading/submit` — 提交批改任务

将 OCR 识别后的题目数据提交给 LLM 进行批改。后台使用 Celery Chord 模式：N 道题并行评分 → 全部完成后自动生成综合报告。

**请求体**:
```json
{
  "task_type": 2,
  "total_pages": 1,
  "original_file": "data/raw_images/abc.jpg",
  "processed_file": "data/processed_images/cleaned_abc.jpg",
  "questions": [
    {
      "page_num": 1,
      "question_index": 0,
      "subject": "数学",
      "question_text": "计算 3+5×2 的结果",
      "question_image": "data/cut_images/cut_task42_q1.jpg",
      "coordinate": { "x1": 100, "y1": 200, "x2": 800, "y2": 400 },
      "full_score": 10.0
    },
    {
      "page_num": 1,
      "question_index": 1,
      "subject": "英语",
      "question_text": "Translate: Hello",
      "question_image": "data/cut_images/cut_task42_q2.jpg",
      "coordinate": { "x1": 100, "y1": 450, "x2": 800, "y2": 600 },
      "full_score": 5.0
    }
  ]
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_type` | int (1-3) | 是 | 1=单题, 2=整页, 3=多页 |
| `total_pages` | int (≥1) | 是 | 总页数 |
| `original_file` | str | 是 | 原始图片路径/URL |
| `processed_file` | str | 否 | 清洗后图片路径/URL |
| `questions` | array | 是 | 至少 1 道题目 |
| `questions[].page_num` | int (≥1) | 是 | 页码 |
| `questions[].question_index` | int (≥0) | 是 | 题号索引（0-based） |
| `questions[].subject` | str | 是 | 学科：数学/语文/英语（或 math/chinese/english） |
| `questions[].question_text` | str | 否 | OCR 识别的问题文本 |
| `questions[].question_image` | str | 否 | 题目裁剪图片路径 |
| `questions[].coordinate` | object | 否 | `{x1, y1, x2, y2}` 边界框 |
| `questions[].full_score` | float (>0) | 是 | 本题满分 |

**响应** (200):
```json
{
  "assignment_task_id": 43,
  "celery_task_id": "a1b2c3d4-e5f6-...",
  "status": 0
}
```

**后续步骤**:
1. 记录返回的 `assignment_task_id`
2. 轮询 `GET /grading/status/{task_id}` 等待 `task_status` 变为 `2`
3. 调用 `GET /grading/result/{task_id}` 获取批改结果

**错误**:
- `422` — OCR 数据校验失败（题目列表为空、分数无效、学科缺失等）

---

#### GET `/grading/status/{task_id}` — 查询任务状态

用于轮询任务是否完成。

**响应** (200):
```json
{
  "assignment_task_id": 43,
  "task_status": 1,
  "task_status_label": "processing",
  "celery_task_id": "a1b2c3d4-...",
  "async_status": 1,
  "retry_count": 0,
  "error_msg": null,
  "created_at": "2026-05-19T10:30:00",
  "finished_at": null
}
```

**轮询建议**: 每隔 2-5 秒查询一次，直到 `task_status` 为 `2` 或 `3`。

**错误**:
- `404` — 任务不存在
- `403` — 无权访问（任务不属于当前用户）

---

#### GET `/grading/result/{task_id}` — 获取批改结果与报告

仅在 `task_status=2` 时可调用。

**响应** (200):
```json
{
  "assignment_task_id": 43,
  "task_status": 2,
  "task_type": 2,
  "questions": [
    {
      "question_index": 0,
      "page_num": 1,
      "subject": "math",
      "question_text": "计算 3+5×2 的结果",
      "is_correct": 1,
      "score": 10.0,
      "full_score": 10.0,
      "error_reason": "",
      "correct_answer": "13",
      "comment": "做得很好！运算顺序正确，先乘后加。"
    }
  ],
  "report": {
    "total_score": 10.0,
    "max_total_score": 10.0,
    "correct_count": 1,
    "total_questions": 1,
    "subject_list": ["math"],
    "page_count": 1,
    "summary": "本次数学作业整体完成良好，计算题掌握了正确的运算顺序...",
    "suggestion": "建议继续巩固四则运算和运算优先级，可以适当增加应用题练习..."
  }
}
```

**`questions[]` 字段**:
| 字段 | 说明 |
|------|------|
| `is_correct` | 1=正确, 0=错误 |
| `score` | LLM 给出的得分 |
| `full_score` | 本题满分 |
| `error_reason` | 错误原因（正确时为空） |
| `correct_answer` | 正确答案 |
| `comment` | 教师风格的评语 |

**`report` 字段**: 由 LLM 聚合所有题目结果后生成的综合报告，包含总体评价和提升建议。

**错误**:
- `404` — 任务不存在
- `403` — 无权访问
- `400` — 任务尚未完成（task_status != 2）

---

#### GET `/grading/tasks` — 获取用户任务列表

**查询参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 20 | 每页数量 |
| `offset` | int | 0 | 偏移量 |

**响应** (200):
```json
{
  "tasks": [
    {
      "assignment_task_id": 43,
      "task_type": 2,
      "total_pages": 1,
      "task_status": 2,
      "task_status_label": "completed",
      "created_at": "2026-05-19T10:30:00",
      "finished_at": "2026-05-19T10:31:00",
      "total_questions": 3
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

## 接口速查表

| Method | Path | Auth | 说明 |
|--------|------|:----:|------|
| POST | `/users/register` | — | 注册并获取 Token |
| POST | `/users/login` | — | 登录并获取 Token |
| GET | `/users/protected` | ✓ | 认证测试 |
| POST | `/images/upload_and_clean` | ✓ | 上传图片 → 自动清洗+OCR |
| POST | `/ocr/process` | ✓ | 手动触发 OCR（通常不需要） |
| POST | `/grading/submit` | ✓ | 提交 OCR 数据 → LLM 批改 |
| GET | `/grading/status/{task_id}` | ✓ | 查询任务状态 |
| GET | `/grading/result/{task_id}` | ✓ | 获取批改结果 |
| GET | `/grading/tasks` | ✓ | 用户任务列表 |

## 典型前端轮询流程

```javascript
// 1. 上传图片
const { task_id } = await fetch('/images/upload_and_clean', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData,
}).then(r => r.json());

// 2. 等待清洗+OCR完成（task_status=2）
let status = 0;
while (status !== 2 && status !== 3) {
  await sleep(3000);
  const res = await fetch(`/grading/status/${task_id}`, {
    headers: { 'Authorization': `Bearer ${token}` },
  }).then(r => r.json());
  status = res.task_status;
}
if (status === 3) throw new Error('处理失败');

// 3. 获取切题结果，组装 grading/submit 请求体
const questions = await fetchQuestionsFromDB(task_id);

// 4. 提交批改
const { assignment_task_id } = await fetch('/grading/submit', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ task_type: 2, total_pages: 1, original_file: '...', questions }),
}).then(r => r.json());

// 5. 轮询批改状态
let gradingStatus = 0;
while (gradingStatus !== 2 && gradingStatus !== 3) {
  await sleep(3000);
  const res = await fetch(`/grading/status/${assignment_task_id}`, {
    headers: { 'Authorization': `Bearer ${token}` },
  }).then(r => r.json());
  gradingStatus = res.task_status;
}

// 6. 获取批改结果
const result = await fetch(`/grading/result/${assignment_task_id}`, {
  headers: { 'Authorization': `Bearer ${token}` },
}).then(r => r.json());
// result.questions[] — 每道题的批改详情
// result.report — 综合报告
```

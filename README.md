# SmartGrader

智能阅卷系统 — 支持图片上传、自动清洗、OCR识别、结构化切题与裁剪。

---

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | 运行环境 |
| MySQL 8.0+ | 持久化存储 |
| Redis 7+ | Celery 消息队列与结果后端 |
| 阿里云 OCR 服务 | 试卷识别 API（需开通） |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填写各项配置：

- **阿里云 OCR**：`ALIBABA_CLOUD_ACCESS_KEY_ID` / `SECRET` / `REGION`
- **MySQL**：编辑 `core/config.py` 中的 `DATABASE_URL`（默认 `mysql+aiomysql://root:root123@localhost:3306/smart_grader`）
- **Redis**：编辑 `core/celery_app.py` 中的 Redis URL（默认 `redis://localhost:6379/2`）

### 3. 启动服务

**终端 1 — API 服务**：

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**终端 2 — Celery 异步任务 Worker**：

```bash
celery -A core.celery_app worker --pool solo --concurrency 2 --loglevel INFO
celery -A core.celery_app worker --pool prefork --concurrency 2 --loglevel INFO
```

> ⚠️ 必须先启动 Redis 和 MySQL，API 才会正常初始化。

---

## 系统架构

### 一次完整的图片处理流程

```
用户上传图片
     │
     ▼
[Router] image_router.py
     │ 保存原始图片 → data/raw_images/
     │ 创建数据库记录 (task_status=0)
     │ 投递 Celery 任务
     ▼
[Worker] process_homework_image_task
     (services/image_service.py)
     │ 灰度化 → 自适应阈值 → 轮廓检测裁剪黑边 → 增强文字
     │ 保存清洗图片 → data/processed_images/
     │ 更新状态 (task_status=2)
     │ 自动投递 OCR 任务
     ▼
[Worker] process_ocr_task
     (services/ocr_service.py)
     │
     ├─ 步骤1: 整页文字识别 (RecognizeEduPaperOcr)
     │   用于展示全文、辅助文本拆分
     │
     ├─ 步骤2: 结构化切题 (RecognizeEduPaperStructed)
     │   返回每道题的文本 + 坐标 + 学科分类
     │   └─ 回退方案: RecognizeEduPaperCut (旧版)
     │
     ├─ 步骤3: 按坐标裁剪题目图片
     │   保存到 data/cut_images/cut_task{id}_q{id}.jpg
     │   └─ 裁剪源 = 原始图片（坐标来自原始图片空间）
     │
     └─ 步骤4: 结果入库
          question_results 表写入每道题
          更新 AssignmentTask 状态为完成 (2)
```

### 关键模块

| 模块 | 文件 | 职责 |
|------|------|------|
| OCR 服务 | `services/ocr_service.py` | 整页识别、结构化切题、坐标提取、图片裁剪、后处理拆分 |
| 图片处理 | `services/image_service.py` | OpenCV 图片清洗（灰度化、二值化、去黑边） |
| 阿里云 SDK | `utils/aliyun_client.py` | 阿里云 OCR 客户端单例 |
| 路由 | `routers/image_router.py` | 图片上传接口 (`POST /images/upload_and_clean`) |
| 模型 | `models/question_result.py` | 题目结果表（含坐标、文本、裁剪图路径） |
| 模型 | `models/assignment_task.py` | 作业任务表（状态机管理） |
| 配置 | `core/config.py` | 全局配置（数据库、阿里云密钥） |

### 数据库表结构

**assignment_tasks**（作业任务主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键，自增 |
| user_id | BIGINT | 关联用户 |
| task_type | SMALLINT | 1=单题 2=整页 3=多页 |
| original_file | VARCHAR | 原始图片 OSS 路径 |
| processed_file | VARCHAR | 清洗后图片 OSS 路径 |
| task_status | SMALLINT | 0=待处理 1=处理中 2=完成 3=失败 |
| error_msg | TEXT | 错误信息 |

**question_results**（题目结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键，自增 |
| task_id | BIGINT | 关联作业任务 |
| page_num | INT | 页码 |
| question_index | INT | 题号（从1开始） |
| question_text | TEXT | OCR 识别文本 |
| question_image | VARCHAR | 裁剪后图片本地路径 |
| coordinate | JSON | 题目在原图中的坐标 {x1,y1,x2,y2} |
| subject | VARCHAR | 学科标签 |
| is_correct | INT | 0=待批改 |

---

## 测试切题功能

### 准备工作

确保 API 和 Celery Worker 都已启动（见上方「快速开始」）。

### 端到端测试脚本

项目提供了 `tests/test_e2e_ocr.py` 端到端测试脚本，一键验证完整流程：

```bash
python tests/test_e2e_ocr.py
```

脚本执行流程：
1. 注册/登录测试用户
2. 上传测试图片 → 获取 task_id
3. 等待 20 秒（Celery 异步处理）
4. 查询数据库验证结果

### 测试图片

测试图片位于 `res/ima/` 目录（项目自带）：

| 图片 | 类型 | 题目数 | 特点 |
|------|------|--------|------|
| `1 (1).jpg` | 物理 | 3 题 | 重力计算，含单位 (N/kg) |
| `1 (2).jpg` | — | — | 备用测试 |
| `1 (3).jpg` | — | — | 备用测试 |
| `1 (4).jpg` | 数学 | 3 题 | 四则运算、混合计算 |
| `1 (5).jpg` | 数学 | 4 题 | 应用题 + 选择题混合 |
| `1 (6).jpg` | 数学 | 5 题 | 二次根式，含 LaTeX 公式 |

### 切换测试图片

编辑 `tests/test_e2e_ocr.py` 中的 `img_path` 即可切换不同图片：

```python
img_path = 'res/ima/1 (6).jpg'
```

### 手动测试流程

如果需更细粒度控制，也可直接通过 API 测试：

```python
import requests

# 1. 获取 token
r = requests.post('http://127.0.0.1:8001/users/login',
    json={'username': 'test', 'password': 'test123'})
TOKEN = r.json()['access_token']

# 2. 上传图片
with open('test.jpg', 'rb') as f:
    r = requests.post('http://127.0.0.1:8001/images/upload_and_clean',
        headers={'Authorization': f'Bearer {TOKEN}'},
        files={'file': ('test.jpg', f, 'image/jpeg')})
print(r.json())  # 返回 task_id

# 3. 等待约 20 秒后查询结果
# 查询 assignment_tasks 表获取状态
# 查询 question_results 表获取切题结果
```

---

## 切题算法详解

### 切题优先级

```
RecognizeEduPaperStructed (精细版)
    │ 成功 → 直接使用
    └─ 失败 (part_info 为空) → RecognizeEduPaperCut (旧版, 回退)
                               ├─ photo 模式
                               └─ scan 模式 (备选)
```

### 坐标提取

- **Structed 格式**：从 `part_info[].subject_list[].pos_list[0]`（第一组多边形）取 x/y 极值组成外接矩形
- **Cut 格式**：从 `page_list[].subject_list[].content_list_info[].pos` 取 x/y 极值

### 后处理文本拆分

当 API 将多道题合并为一道时，`_split_merged_questions()` 会按以下规则拆分：

1. 题号检测：`(?<!\d)(\d+)[.、．]` — 识别 `1.` `2、` 等题号
2. 新题关键词：`某[石块体积为]` `有一?[块个段小]` 等
3. 坐标按文本长度等比拆分 y 方向

### 缺失题号恢复

当题目以 LaTeX 公式（`$$`）开头时，API 可能丢失题号前缀。
`_recover_missing_numbers()` 会根据上一题题号自动补全，例如：

```
恢复前: $$\frac { \sqrt { 2 - x } } ...
恢复后: 2.$$\frac { \sqrt { 2 - x } } ...
```

### 坐标空间说明

- 切题 API 调用时使用 **原始图片**，返回的坐标为原始图片空间
- 裁剪题目图片时同样使用 **原始图片** 作为裁剪源，保证坐标映射准确
- 清洗后图片（二值化）仅用于提高文字识别质量，不参与坐标计算

---

## 常见问题

### Q: API 返回 500 Internal Server Error

**原因**：API 服务异常。查看终端日志定位具体错误。

常见错误：
- `content_type is None`：上传文件时未指定 MIME 类型，确保 `files={'file': (name, f, 'image/jpeg')}`
- 数据库连接失败：检查 MySQL 是否启动、`DATABASE_URL` 配置是否正确
- Redis 连接失败：检查 Redis 是否启动

### Q: 上传后长时间等待，task_status 仍为 0（待处理）

**原因**：Celery Worker 未启动或未正确连接 Redis。

```bash
# 检查 Worker 日志是否有 "celery@xxx ready."
# 检查 Redis 是否运行
redis-cli ping  # 应返回 PONG
```

### Q: 切题结果为 0 题

**原因**：
- 图片不包含结构化试题（如手写作文、纯图片）
- 阿里云 API 未识别到题目
- 可检查 Celery Worker 日志是否有「结构化切题成功」字样
- 尝试换一张标准试卷图片测试

### Q: 裁剪图片坐标偏差

**原因**：坐标空间不匹配。如果出现裁剪宽度远小于坐标宽度，说明裁剪源图和坐标来自不同图片空间。

从 v1.2 起默认使用原始图片作为裁剪源，如仍有问题请检查 `process_ocr_task` 中的 `crop_source_path` 设置。

---

## 目录结构

```
├── main.py                    # FastAPI 入口
├── core/
│   ├── config.py              # 全局配置
│   ├── database.py            # 数据库会话 (async + sync)
│   ├── celery_app.py          # Celery 应用配置
│   └── auth.py                # JWT 认证
├── models/
│   ├── assignment_task.py     # 作业任务模型
│   ├── question_result.py     # 题目结果模型
│   ├── async_task.py          # 异步日志模型
│   └── user.py                # 用户模型
├── routers/
│   ├── image_router.py        # 图片上传与处理路由
│   └── user_router.py         # 用户认证路由
├── services/
│   ├── image_service.py       # OpenCV 图片清洗 + 触发 OCR
│   ├── ocr_service.py         # 阿里云 OCR 识别 + 切题 + 裁剪
│   └── user_service.py        # 用户业务逻辑
├── utils/
│   ├── aliyun_client.py       # 阿里云 SDK 客户端
│   ├── key_generator.py       # 唯一键生成
│   └── password_util.py       # 密码加密
├── schemas/
│   ├── image_schemas.py       # 图片相关 Pydantic 模型
│   └── user_schemas.py        # 用户相关 Pydantic 模型
├── res/
│   └── ima/                    # 测试图片（6张，覆盖物理/数学题型）
├── tests/
│   └── test_e2e_ocr.py        # OCR 端到端测试
├── data/
│   ├── raw_images/            # 原始上传图片
│   ├── processed_images/      # 清洗后图片
│   └── cut_images/            # 裁剪后的题目图片
├── .env.example               # 环境变量模板
└── requirements.txt
```

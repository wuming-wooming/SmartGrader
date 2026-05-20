# 百度云教育场景OCR API 调用技术文档

> **面向接口**：试卷切题识别 + 试卷分析与识别
> **文档版本**：2026-05-20


## 一、认证机制

### 1.1 Access Token 获取

百度云OCR采用OAuth2.0 `client_credentials` 模式认证，通过 API Key + Secret Key 换取 access_token，有效期 **30天（2592000秒）**。

```
POST https://aip.baidubce.com/oauth/2.0/token
```

**请求参数**（URL query string）：

| 参数 | 值 |
|------|-----|
| `grant_type` | `client_credentials`（固定值）|
| `client_id` | 应用的 API Key |
| `client_secret` | 应用的 Secret Key |

**成功响应示例**：
```json
{
    "access_token": "24.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "expires_in": 2592000,
    "scope": "...",
    "refresh_token": "25.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

> **⚠️ 关键约束**：个人免费额度 QPS 限制为 **2次/秒**，开通按量付费后提升至 10次/秒。

**Python 代码实现**（以原始 HTTP 请求为例）：
```python
import requests

def get_access_token(api_key: str, secret_key: str) -> tuple[str, int]:
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if "access_token" in data:
            return data["access_token"], data["expires_in"]
        else:
            raise Exception(f"获取token失败: {data}")
    else:
        raise Exception(f"HTTP错误: {response.status_code}")

# Token 缓存策略：存入内存，过期前自动刷新
```


## 二、接口 1：试卷切题识别

### 2.1 基本信息

对试卷图片进行题目自动切分与结构化识别，输出包含题干、选项、答案等要素的 JSON。

| 项目 | 内容 |
|------|------|
| 请求方法 | `POST` |
| 请求 URL | `https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu` |
| URL 参数 | `access_token={通过认证接口获取的token}` |
| Content-Type | `application/x-www-form-urlencoded` |

### 2.2 请求参数（Body，x-www-form-urlencoded）

| 参数 | 必选 | 类型 | 说明 |
|------|------|------|------|
| `image` | 三选一 | string | 图片Base64编码后进行urlencode。大小≤10M，最短边≥15px，最长边≤8192px。支持 jpg/jpeg/png/bmp |
| `url` | 三选一 | string | 图片URL（长度≤1024字节），需关闭防盗链 |
| `pdf_file` | 三选一 | string | PDF文件Base64编码后urlencode，仅识别单页PDF的第一页 |
| `pdf_file_num` | 否 | string | PDF页码（pdf_file有效时生效，默认第1页）|
| `language_type` | 否 | string | `CHN_ENG`（默认）/ `ENG` |
| `detect_direction` | 否 | string | 是否检测朝向：`true` / `false`（默认） |
| `words_type` | 否 | string | **`handprint_mix`（默认，手写印刷混排）** / `handwring_only`（纯手写） |
| `splice_text` | 否 | string | 是否拼接每行文本：`true`（耗时+1s）/ `false`（默认） |
| `enhance` | 否 | string | 是否图像矫正增强：`true` / `false`（默认） |
| `only_split` | 否 | string | 是否仅切分不识别：`true` / `false`（默认） |

> **优先级**：`image` > `url` > `pdf_file`，高优先级字段存在时低优先级字段失效。

### 2.3 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `log_id` | uint64 | 唯一 log ID，用于问题定位 |
| `direction` | int32 | 图像朝向（仅`detect_direction=true`时返回）：0=正向, 1=逆90°, 2=逆180°, 3=逆270° |
| `qus_result_num` | int32 | 识别题目结果数 |
| `qus_result` | array | 切题结果数组 |
| `qus_figure` | array | 试卷内题目图片信息 |
| `pdf_file_size` | int32 | PDF总页数（仅pdf_file参数有效时返回） |

**`qus_result[i]` 子字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `qus_type` | int32 | 题目类型：0=选择题, 1=判断题, 2=填空题, 3=问答题, 4=其他 |
| `qus_probability` | float | 题目置信度 |
| `qus_location` | array | 题目区域四角点坐标（左上为原点，顺时针） |
| `elem_text` | object | 题目各元素拼接文本（仅`splice_text=true`时返回） |
| `qus_element` | array | 题目元素列表 |

**`qus_element[j]` 子字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `elem_type` | int32 | 元素类型：0=题干, 1=子题, 2=答案, 3=选项, 4=配图, 5=参考答案 |
| `elem_probability` | float | 元素置信度 |
| `elem_location` | array | 元素位置四角点坐标 |
| `elem_word` | array | 该元素的文字行信息 |
| `elem_word[k].word` | string | 行文字内容 |
| `elem_word[k].word_type` | string | `handwriting`（手写）/ `print`（印刷） |
| `elem_word[k].word_location` | array | 行位置四角点坐标 |

**`elem_text` 子字段**（仅当 `splice_text=true`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `stem_text` | string | 题干文本 |
| `subqus_text` | string | 子题文本 |
| `answer_text` | string | 答案文本 |
| `option_text` | string | 选项文本（仅选择题） |
| `interpretation_text` | string | 参考答案文本 |


## 三、接口 2：试卷分析与识别

### 3.1 基本信息

对文档版面进行分析，输出图、表、标题、文本的位置，并输出分版块内容的OCR识别结果，支持中英文手写印刷混排、公式识别、手写竖式识别。

| 项目 | 内容 |
|------|------|
| 请求方法 | `POST` |
| 请求 URL | `https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis` |
| URL 参数 | `access_token={通过认证接口获取的token}` |
| Content-Type | `application/x-www-form-urlencoded` |

### 3.2 请求参数（Body，x-www-form-urlencoded）

| 参数 | 必选 | 类型 | 说明 |
|------|------|------|------|
| `image` | 三选一 | string | 图片Base64编码后urlencode。大小≤10M，最短边≥15px，最长边≤8192px |
| `url` | 三选一 | string | 图片URL，需关闭防盗链 |
| `pdf_file` | 三选一 | string | PDF文件Base64编码后urlencode |
| `language_type` | 否 | string | `CHN_ENG` / `ENG`（默认`CHN_ENG`） |
| `detect_direction` | 否 | string | 是否检测图像朝向：`true` / `false`（默认） |
| `words_type` | 否 | string | **`handprint_mix`（手写印刷混排，默认）** / `handwring_only` / `print` |
| `detect_layout` | 否 | string | 是否分析文档版面：`true` / `false`（默认） |
| `detect_formula` | 否 | string | 是否识别公式：`true` / `false`（默认） |

> **⚠️ 注意**：试卷分析与识别接口的响应结构为版面分析结果 + 各版块OCR文本，与试卷切题的题目结构化JSON不同。如果下游LLM批阅需要题目级别的结构化数据，建议优先使用试卷切题接口；如果需要更完整的版面文字内容，可使用本接口作为补充。

### 3.3 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `log_id` | uint64 | 唯一log id |
| `results_num` | int32 | 识别结果数 |
| `results` | array | 版面分析及OCR结果数组 |

**`results[i]` 子字段**（核心）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `words_type` | string | 文字属性：`handwring_only` / `print` / `handprint_mix` |
| `words` | object | 识别文本及位置 |
| `words.word` | string | 该行文字内容 |
| `words.location` | array | 文字位置四角点坐标 |
| `tables` | array | 表格识别结果（如有） |
| `formulas` | array | 公式识别结果（如有，Latex格式） |
| `figures` | array | 图形信息（如有） |

> **提示**：调用时建议设置 `detect_layout=true` 和 `detect_formula=true` 以获取最完整的版面信息和公式内容。


## 四、通用错误码速查

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| 0 | 成功 | - |
| 18 | QPS 超限 | 等待 1-3s 后重试（指数退避） |
| 17 | 每天请求量超限 | 检查免费额度余量 |
| 19 | 请求总量超限额 | 需购买次数包或开通按量付费 |
| 110 | Access Token 无效 | 检查 token 是否正确 |
| 111 | Access Token 过期 | 自动刷新 token 后重试 |
| 216100 | 请求参数非法 | 检查参数格式和值 |
| 216101 | 缺少必须参数 | 补充缺失参数 |
| 216200 | 图片为空 | 检查图片数据是否有效 |
| 216201 | 图片格式错误 | 仅支持 PNG/JPG/JPEG/BMP |
| 216202 | 图片大小超限 | Base64编码后≤10M，分辨率≤8192×8192 |
| 216630 | 识别错误 | 重试，持续出现联系技术支持 |
| 282000 | 服务器内部错误 | 可能图片文字过多超时，重试或切割图片 |
| 282003 | 请求参数缺失 | 补充缺失的参数名 |

QPS相关：免费额度并发限制为 **2QPS**；错误码 18 触发时需指数退避重试；错误码 17/19 时需要检查配额余量或升级付费计划。


## 五、请求构造示例（Python 原生 HTTP）

### 5.1 图片转 Base64 + urlencode

```python
import base64
import urllib.parse

def image_to_base64_urlencode(image_path: str) -> str:
    with open(image_path, "rb") as f:
        img_data = f.read()
    base64_str = base64.b64encode(img_data).decode("utf-8")
    return urllib.parse.quote_plus(base64_str)
```

### 5.2 试卷切题识别请求

```python
import requests

def call_paper_cut(access_token: str, image_path: str, 
                   splice_text: bool = True, words_type: str = "handprint_mix"):
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu?access_token={access_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    image_b64 = image_to_base64_urlencode(image_path)
    
    data = {
        "image": image_b64,
        "language_type": "CHN_ENG",
        "words_type": words_type,
        "splice_text": str(splice_text).lower()
    }
    
    response = requests.post(url, data=data, headers=headers)
    return response.json()
```

### 5.3 试卷分析与识别请求

```python
def call_doc_analysis(access_token: str, image_path: str,
                      detect_layout: bool = True, detect_formula: bool = True,
                      words_type: str = "handprint_mix"):
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis?access_token={access_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    image_b64 = image_to_base64_urlencode(image_path)
    
    data = {
        "image": image_b64,
        "language_type": "CHN_ENG",
        "words_type": words_type,
        "detect_layout": str(detect_layout).lower(),
        "detect_formula": str(detect_formula).lower()
    }
    
    response = requests.post(url, data=data, headers=headers)
    return response.json()
```

### 5.4 带 Token 缓存的完整客户端示例

```python
import time
import random

class BaiduOCRClient:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self._token = None
        self._token_expires_at = 0
    
    def _ensure_token(self):
        """确保token有效，过期自动刷新"""
        if self._token is None or time.time() > self._token_expires_at - 3600:
            token, expires_in = get_access_token(self.api_key, self.secret_key)
            self._token = token
            self._token_expires_at = time.time() + expires_in
    
    def _call_with_retry(self, url: str, data: dict, max_retries: int = 3):
        """带指数退避重试的请求包装"""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        for attempt in range(max_retries):
            self._ensure_token()
            full_url = f"{url}?access_token={self._token}"
            
            response = requests.post(full_url, data=data, headers=headers)
            result = response.json()
            
            error_code = result.get("error_code")
            if error_code is None:
                return result  # 成功
            
            if error_code in (110, 111):  # Token过期
                self._token = None  # 强制刷新
                continue
            elif error_code == 18:  # QPS超限
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
                continue
            elif error_code in (17, 19):
                raise Exception(f"配额超限: {result.get('error_msg')}")
            else:
                raise Exception(f"API错误 {error_code}: {result.get('error_msg')}")
        
        raise Exception("重试次数已耗尽")
    
    def cut_paper(self, image_path: str, splice_text: bool = True, 
                  words_type: str = "handprint_mix") -> dict:
        url = "https://aip.baidubce.com/rest/2.0/ocr/v1/paper_cut_edu"
        data = {
            "image": image_to_base64_urlencode(image_path),
            "language_type": "CHN_ENG",
            "words_type": words_type,
            "splice_text": str(splice_text).lower()
        }
        return self._call_with_retry(url, data)
    
    def analyze_doc(self, image_path: str, detect_layout: bool = True,
                    detect_formula: bool = True, 
                    words_type: str = "handprint_mix") -> dict:
        url = "https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis"
        data = {
            "image": image_to_base64_urlencode(image_path),
            "language_type": "CHN_ENG",
            "words_type": words_type,
            "detect_layout": str(detect_layout).lower(),
            "detect_formula": str(detect_formula).lower()
        }
        return self._call_with_retry(url, data)
```


## 六、与阿里云OCR的关键差异

| 维度 | 阿里云（旧） | 百度云（新） |
|------|------------|------------|
| 认证方式 | AK+SK + HMAC-SHA1签名 | AK+SK → access_token（30天） |
| Content-Type | `application/json` | `application/x-www-form-urlencoded` |
| 图片传参 | JSON内`ImageBase64`字段 | 表单`image`字段（需urlencode） |
| 手写支持 | 有限（约68%） | 专门优化，手写印刷混排识别良好 |
| 手写体识别准确率 | 约68% | 手写字符准确率提升至95.6% |
| 免费额度 | 约200次/月 | 500次/月（教育场景接口） |
| 免费 QPS | 约5 | 2（开通按量付费后10） |
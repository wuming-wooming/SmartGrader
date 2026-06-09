// ============================================================
// 答辩演示幻灯片数据
// 所有演示内容集中存储于此，方便修改
// ============================================================

export interface ContentBlock {
  type: 'title' | 'subtitle' | 'text' | 'bullet' | 'highlight' | 'code'
  text: string
  children?: ContentBlock[]
}

export interface SlideImage {
  src: string
  alt?: string
  position?: 'left' | 'center' | 'right'
  size?: 'small' | 'medium' | 'large'
  animate?: 'float' | 'fade-in' | 'none'
}

export interface Slide {
  id: number
  title: string
  subtitle?: string
  layout: 'cover' | 'content' | 'two-column' | 'end'
  contents: ContentBlock[]
  images?: SlideImage[]
  speakerNotes?: string
}

export const presentationSlides: Slide[] = [
  // ==================== 第1页：封面 ====================
  {
    id: 1,
    title: 'SmartGrader',
    subtitle: '智能作业批改系统',
    layout: 'cover',
    contents: [
      { type: 'title', text: 'SmartGrader' },
      { type: 'subtitle', text: '智能作业批改系统' },
      { type: 'text', text: 'Python 课程结课项目答辩' },
      { type: 'text', text: '童天宇 | 罗東明 | 周康哲' },
    ],
    speakerNotes: '开场介绍项目名称和组员',
  },

  // ==================== 第2页：项目定位 ====================
  {
    id: 2,
    title: '项目定位',
    layout: 'content',
    contents: [
      { type: 'highlight', text: '以学生的视角，模拟真实企业级服务开发场景' },
      { type: 'text', text: '本项目更侧重于 Python 网络服务后端实践，涵盖从架构设计、技术选型到模块解耦、架构演进的完整开发流程。' },
      {
        type: 'bullet', text: '核心目标：',
        children: [
          { type: 'bullet', text: '理解企业级后端服务架构设计' },
          { type: 'bullet', text: '实践模块解耦与设计模式' },
          { type: 'bullet', text: '掌握异步任务调度与消息队列' },
          { type: 'bullet', text: '体验真实项目的架构演进过程' },
        ],
      },
    ],
    speakerNotes: '略讲项目定位 — 学生视角的企业级实践',
  },

  // ==================== 第3页：侧重点 ====================
  {
    id: 3,
    title: '项目侧重点',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '后端架构设计',
        children: [
          { type: 'bullet', text: '分层架构：MVC + 数据访问层 + 异步任务层' },
          { type: 'bullet', text: '模块解耦：「依赖抽象而非具体」，高内聚低耦合' },
        ],
      },
      {
        type: 'bullet', text: '架构演进',
        children: [
          { type: 'bullet', text: '固定流程 → 管道化可配置流程' },
          { type: 'bullet', text: '依赖单一服务商 → 依赖抽象（适配器模式）' },
          { type: 'bullet', text: '服务模块级隔离 → 服务项目级隔离（微服务理念）' },
        ],
      },
      {
        type: 'bullet', text: '弹性与容灾',
        children: [
          { type: 'bullet', text: '弹性支持：高可扩展性设计' },
          { type: 'bullet', text: '容灾备份：熔断、降级、隔离' },
          { type: 'bullet', text: '高并发：线程池 + 消息队列削峰填谷' },
        ],
      },
    ],
    speakerNotes: '中讲 — 后端架构、架构演进、弹性容灾、高并发',
  },

  // ==================== 第4页：后端服务分层 ====================
  {
    id: 4,
    title: '后端服务分层',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '基础层（MVC 扩展）：',
        children: [
          { type: 'bullet', text: 'Models  — 数据实体层（SQLAlchemy ORM）' },
          { type: 'bullet', text: 'Repositories — 数据访问层（封装 CRUD）' },
          { type: 'bullet', text: 'Schemas — 视图层（Pydantic 序列化/验证）' },
          { type: 'bullet', text: 'Services — 服务层（核心业务逻辑）' },
          { type: 'bullet', text: 'Tasks — 异步任务层（Celery 任务）' },
          { type: 'bullet', text: 'Routers — 路由层（API 端点定义）' },
        ],
      },
      {
        type: 'bullet', text: '辅助模块：',
        children: [
          { type: 'bullet', text: 'Core — 核心配置（Config、Database、Auth、Celery）' },
          { type: 'bullet', text: 'Utils — 工具类（密码加密、阿里云/百度云客户端）' },
        ],
      },
    ],
    speakerNotes: '略讲分层架构，一张图展示清楚即可',
  },

  // ==================== 第5页：技术路线1 ====================
  {
    id: 5,
    title: '技术路线与架构演进（一）',
    subtitle: '路线1：初始架构',
    layout: 'content',
    contents: [
      { type: 'text', text: '图像清洗 → 阿里云OCR → 纯文本单题LLM批阅 → LLM复核报告生成' },
      {
        type: 'highlight',
        text: '⚠️ 问题：阿里云OCR效果不佳，纯文本批阅准确率波动大（受OCR效果影响极大）',
      },
      {
        type: 'bullet', text: '架构特点：',
        children: [
          { type: 'bullet', text: '硬编码流程，固定图像处理步骤' },
          { type: 'bullet', text: '强依赖单一 OCR 服务商（阿里云）' },
          { type: 'bullet', text: '单一 LLM 批阅策略（纯文本）' },
        ],
      },
    ],
    speakerNotes: '细讲路线1 — 初始架构及其问题',
  },

  // ==================== 第6页：技术路线2 ====================
  {
    id: 6,
    title: '技术路线与架构演进（二）',
    subtitle: '路线2：架构优化与解耦',
    layout: 'content',
    contents: [
      { type: 'text', text: '图像清洗管道 → OCR抽象引擎 → 单题LLM批阅策略 → LLM复核报告生成' },
      {
        type: 'bullet', text: '图像清洗流程管道化：',
        children: [
          { type: 'bullet', text: '定义 ImagePipeline 基类 + 解析器解析 JSON 配置' },
          { type: 'bullet', text: '灵活调整处理流程的先后顺序与参数' },
        ],
      },
      {
        type: 'bullet', text: 'OCR 引擎适配器：',
        children: [
          { type: 'bullet', text: '抽象 OcrEngine 基类，封装 OCR 操作' },
          { type: 'bullet', text: '根据全局配置切换服务商，支持未来扩展' },
        ],
      },
      {
        type: 'bullet', text: 'LLM 批阅策略选择：',
        children: [
          { type: 'bullet', text: 'GradingStrategy 基类抽象批阅功能' },
          { type: 'bullet', text: '支持静态/动态切换策略（纯文本 / 多模态）' },
        ],
      },
    ],
    speakerNotes: '细讲路线2 — 三个核心解耦点',
  },

  // ==================== 第7页：技术路线3 ====================
  {
    id: 7,
    title: '技术路线与架构演进（三）',
    subtitle: '路线3：百度智能批阅接入',
    layout: 'content',
    contents: [
      { type: 'text', text: '百度智能作业批阅接口 → 切题结果下载 → 单题LLM复核批阅 → LLM复核报告生成' },
      {
        type: 'highlight',
        text: '✅ 相对独立于前两条路线，批阅准确率更高（百度智能批阅接口）',
      },
      {
        type: 'bullet', text: '关键点：',
        children: [
          { type: 'bullet', text: '复用已有的 LLM 批阅流程，新增策略即可' },
          { type: 'bullet', text: '策略模式使新路线接入成本极低' },
          { type: 'bullet', text: '与路线1/2 共享复核报告生成模块' },
        ],
      },
    ],
    speakerNotes: '细讲路线3 — 百度接口接入，展示可扩展性价值',
  },

  // ==================== 第8页：设计模式 ====================
  {
    id: 8,
    title: '设计模式运用汇总',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '适配器模式 — OCR 引擎适配（阿里云 / 百度云）',
      },
      {
        type: 'bullet', text: '策略模式 — LLM 批阅策略切换（纯文本 / 多模态 / 百度复核）',
      },
      {
        type: 'bullet', text: '工厂模式 — 动态创建 OCR 引擎、批阅策略实例',
      },
      {
        type: 'bullet', text: '单例模式 — 全局配置管理、数据库连接池',
      },
      {
        type: 'bullet', text: '组合模式 — 图像处理管道的流程嵌套',
      },
      {
        type: 'bullet', text: '命令模式 — Celery 异步任务封装',
      },
      {
        type: 'bullet', text: '责任链模式 — 图像清洗管道按序处理',
      },
      {
        type: 'bullet', text: '模板方法模式 — 管道基类定义处理骨架',
      },
    ],
    speakerNotes: '略讲设计模式，快速过一遍',
  },

  // ==================== 第9页：项目依赖 ====================
  {
    id: 9,
    title: '项目依赖',
    layout: 'two-column',
    contents: [
      {
        type: 'bullet', text: '后端核心：',
        children: [
          { type: 'bullet', text: 'FastAPI — 后端主框架' },
          { type: 'bullet', text: 'Celery — 异步消息队列' },
          { type: 'bullet', text: 'LangChain — LLM 调用' },
          { type: 'bullet', text: 'OpenCV — 图像处理' },
        ],
      },
      {
        type: 'bullet', text: '数据与认证：',
        children: [
          { type: 'bullet', text: 'MySQL — 关系型数据库' },
          { type: 'bullet', text: 'Redis — 缓存 / Celery Broker' },
          { type: 'bullet', text: 'Jose + Passlib — JWT 认证与加密' },
        ],
      },
      {
        type: 'bullet', text: '辅助工具：',
        children: [
          { type: 'bullet', text: 'Requests — HTTP 调用 OCR' },
          { type: 'bullet', text: 'dotenv — .env 配置加载' },
        ],
      },
      {
        type: 'bullet', text: '前端：',
        children: [
          { type: 'bullet', text: 'Vue 3 + Vite — 前端框架' },
          { type: 'bullet', text: 'Element Plus — UI 组件库' },
          { type: 'bullet', text: 'Axios — HTTP 客户端' },
        ],
      },
    ],
    speakerNotes: '略讲 — 展示技术栈全貌',
  },

  // ==================== 第10页：服务例程 ====================
  {
    id: 10,
    title: '服务例程',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '运行时需启动 5 个服务进程：',
      },
      {
        type: 'bullet', text: 'MySQL — 数据存储服务',
      },
      {
        type: 'bullet', text: 'Redis — 缓存 & Celery Broker',
      },
      {
        type: 'bullet', text: 'Uvicorn — FastAPI 后端主服务（端口 8001）',
      },
      {
        type: 'bullet', text: 'Celery Worker — 异步任务处理',
      },
      {
        type: 'bullet', text: 'Vite — 前端开发服务器（端口 5173，代理 API 到 8001）',
      },
      {
        type: 'highlight',
        text: '📋 总计 5 个进程协同工作，前后端分离 + API 代理',
      },
    ],
    speakerNotes: '略讲 — 5个服务进程概览',
  },

  // ==================== 第11页：遇到的问题 ====================
  {
    id: 11,
    title: '遇到的问题与解决方案',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '问题1：OCR 识别不准确',
        children: [
          { type: 'bullet', text: '从单一阿里云 → 支持百度云切换' },
          { type: 'bullet', text: '抽象 OCR 引擎适配器，提高可扩展性' },
        ],
      },
      {
        type: 'bullet', text: '问题2：同步/异步混用（最大坑）',
        children: [
          { type: 'bullet', text: 'Celery + eventlet 协程下，asyncio 导致任务中断、数据库连接泄露' },
          { type: 'bullet', text: '解决：改异步数据库操作为同步，弃用 eventlet → solo/prefork' },
        ],
      },
      {
        type: 'bullet', text: '问题3：图像清洗效果不理想',
        children: [
          { type: 'bullet', text: '处理流程重构为可配置管道，灵活调整' },
          { type: 'bullet', text: '但因调参未完成，最终将管道设为空（不处理）' },
        ],
      },
    ],
    speakerNotes: '中讲 — 三个核心问题及解决方案，重点讲Celery的坑',
  },

  // ==================== 第12页：拓展方向 ====================
  {
    id: 12,
    title: '未来拓展方向',
    layout: 'content',
    contents: [
      {
        type: 'bullet', text: '弹性拓展',
        children: [
          { type: 'bullet', text: '适配更多 OCR 服务商（腾讯云、华为云…）' },
          { type: 'bullet', text: '增加更多 LLM 批阅场景策略' },
          { type: 'bullet', text: '持续优化批阅提示词' },
        ],
      },
      {
        type: 'bullet', text: '静态配置动态化与容错升级',
        children: [
          { type: 'bullet', text: '静态配置切换 → 按需动态选择' },
          { type: 'bullet', text: '实现熔断与回退逻辑（A 服务不可用 → 自动切 B）' },
        ],
      },
      {
        type: 'bullet', text: '微服务化',
        children: [
          { type: 'bullet', text: '拆分单一项目为多个独立微服务' },
          { type: 'bullet', text: 'Nginx / Spring Cloud Gateway 做网关' },
          { type: 'bullet', text: 'HTTP / gRPC 服务间通讯 + 负载均衡' },
        ],
      },
    ],
    speakerNotes: '中讲 — 三个拓展方向，展示项目潜力',
  },

  // ==================== 第13页：工作划分与统计 ====================
  {
    id: 13,
    title: '项目工作划分与统计',
    layout: 'two-column',
    contents: [
      {
        type: 'bullet', text: '工作划分：',
        children: [
          { type: 'bullet', text: '童天宇（组长）：系统架构、技术选型、认证模块、LLM 批阅、架构演进重构、Bugfix' },
          { type: 'bullet', text: '罗東明：OCR 识别核心、切题算法改进、图片获取接口、联调测试、Bugfix' },
          { type: 'bullet', text: '周康哲：本地图像处理与保存、前端构建与前后端适配' },
        ],
      },
      {
        type: 'bullet', text: '项目统计（截至6月9日）：',
        children: [
          { type: 'bullet', text: 'Python 文件数：50+' },
          { type: 'bullet', text: '总代码量：16,000+ 行（Python 约 80%）' },
          { type: 'bullet', text: '总提交数：55' },
          { type: 'bullet', text: '合并 PR 数：12' },
          { type: 'bullet', text: '项目周期：5月13日 — 6月9日（约4周）' },
        ],
      },
    ],
    speakerNotes: '略讲 — 展示团队分工和项目规模',
  },

  // ==================== 第14页：致谢 ====================
  {
    id: 14,
    title: '',
    layout: 'end',
    contents: [
      { type: 'title', text: '感谢聆听' },
      { type: 'subtitle', text: 'SmartGrader 智能作业批改系统' },
      { type: 'text', text: '欢迎提问与交流' },
    ],
    speakerNotes: '结束页，准备回答提问',
  },
]

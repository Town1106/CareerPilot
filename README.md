# CareerPilot

<p align="center">
  <strong>基于证据链的求职准备与面试训练智能助理</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React 19">
  <img src="https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/LangGraph-✓-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Qdrant-✓-DC244C?logo=qdrant&logoColor=white" alt="Qdrant">
  <img src="https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT">
</p>

---

## 项目简介

CareerPilot 是一个面向软件开发者的求职准备平台，通过 **RAG 证据链**、**JD 能力差距分析**、**自适应模拟面试** 和 **动态学习计划** 形成完整的求职准备闭环。

### 与传统求职工具的区别

| 传统工具 | CareerPilot |
|----------|-------------|
| 润色简历，可能编造经历 | 从用户真实项目资料中提取证据，引用原文 |
| 固定题库随机播放 | 根据目标 JD 缺口动态生成追问 |
| 每次对话独立，无法追踪 | 长期记录薄弱知识点，动态调整学习计划 |
| 回答无引用依据 | 所有关键结论附带页码和原文引用 |
| 无执行过程观测 | 完整 Agent 执行轨迹，记录 Token 用量和延迟 |

### 核心闭环

```
目标岗位 → JD 能力抽取 → 简历与项目证据匹配
    → 能力差距分析 → 学习计划生成
    → 自适应模拟面试 → 评分与能力记忆
    → 动态调整下一轮计划
```

---

## 功能模块

| 模块 | 说明 |
|------|------|
| **知识库管理** | 上传 PDF/DOCX/TXT/Markdown，SHA-256 去重，版本管理，自动向量化索引 |
| **RAG 问答** | Dense + Sparse + RRF 混合检索，带页码级引用 `[S1]` 的证据回答 |
| **JD 能力差距分析** | 结构化抽取岗位要求，原子化归一，RAG 证据匹配，加权覆盖率计算 |
| **公司面经检索** | 百炼联网搜索公开面经，来源白名单校验，7 天缓存，支持真实/混合题库 |
| **模拟面试** | 基于 JD 缺口 + 公司面经的动态追问，独立评分报告，能力记忆沉淀 |
| **学习计划** | LLM 自动生成每日任务，根据面试表现动态调整优先级 |
| **运行轨迹** | 每次 AI 操作的完整记录：节点时间线、Token 用量、检索 Chunk |
| **Skill 注册中心** | 可版本化 Skill 定义，约束触发条件、输入和允许工具 |
| **Tool Policy 引擎** | 工具注册、风险分级、审批策略，写操作需用户批准 |
| **GitHub MCP** | 连接仓库，浏览 README/Commits，导入知识库，提取项目事实 |
| **Calendar MCP** | 学习计划任务一键同步到日历 |
| **LangGraph 状态机** | 多节点 Agent 工作流，条件路由，SSE 实时推送 |
| **简历一致性校验** | 提取 GitHub 项目事实，与简历内容比对，输出匹配/缺失/矛盾报告 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React 19 + Vite)           │
│  Workspace │ Documents │ Jobs │ Interviews │ Plans       │
│  Traces │ Skills │ Tools │ GitHub │ Analysis            │
├─────────────────────────────────────────────────────────┤
│              FastAPI Backend (Python 3.12)               │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Auth     │  │ Harness  │  │ MCP Clients           │  │
│  │ Session  │  │ LangGraph│  │ GitHub · Calendar     │  │
│  │ Argon2   │  │ + SSE    │  │ JSON-RPC 2.0 / HTTP   │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ RAG      │  │ Jobs     │  │ Skills & Tools        │  │
│  │ Dense+   │  │ JD       │  │ Registry · Policy     │  │
│  │ Sparse   │  │ Analysis │  │ Engine · Approvals    │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Interview │  │ Plans    │  │ Traces                │  │
│  │ Adaptive │  │ Dynamic  │  │ Agent Run · Steps     │  │
│  │ Q&A      │  │ Schedule │  │ Token & Latency       │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Data Layer                              │
│  ┌────────────────┐  ┌──────────────────────────────┐  │
│  │ PostgreSQL 18  │  │ Qdrant (Local)               │  │
│  │ 业务事实来源    │  │ Dense + Sparse 向量检索      │  │
│  └────────────────┘  └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  AI Services                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 百炼 DashScope (Qwen 3.7)                        │  │
│  │ · Chat: qwen3.7-plus                             │  │
│  │ · Embedding: qwen3.7-text-embedding (1024d)      │  │
│  │ · Web Search: 联网面经检索                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### LangGraph 工作流（以 JD 分析为例）

```
        ┌──────────┐
        │  extract  │  结构化抽取 JD 要求
        └────┬─────┘
             ▼
        ┌──────────┐
        │ normalize │  别名归一化、原子化拆分
        └────┬─────┘
             ▼
        ┌──────────────┐
        │retrieve_evidence│  为每项要求检索知识库证据
        └──────┬───────┘
               ▼
        ┌──────────┐
        │  judge   │  LLM 核验覆盖度（covered/partial/uncovered/conflict）
        └────┬─────┘
             ▼
           END
```

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+（或使用 SQLite 开发）
- 百炼 API Key（[申请地址](https://bailian.console.aliyun.com/)）

### 1. 克隆项目

```bash
git clone https://github.com/Town1106/CareerPilot.git
cd CareerPilot
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入必要配置：

```ini
# 数据库（默认使用 SQLite，无需配置；PostgreSQL 按需启用）
DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/careerpilot

# 百炼 API（必填）
DASHSCOPE_API_KEY=sk-your-api-key
DASHSCOPE_CHAT_MODEL=qwen3.7-plus
DASHSCOPE_EMBEDDING_MODEL=qwen3.7-text-embedding

# GitHub 集成（可选）
GITHUB_TOKEN=github_pat_xxx

# Calendar MCP（可选，留空使用 Mock 模式）
CALENDAR_MCP_COMMAND=
```

### 3. 启动后端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

后端运行在 http://127.0.0.1:8000，API 文档 http://127.0.0.1:8000/docs。

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173。

### 5. 填充演示数据（可选）

```bash
cd backend
uv run python -m app.scripts.demo_data
```

> 详见 [演示数据说明](#演示数据)。

---

## 项目结构

```
CareerPilot/
├── backend/
│   ├── app/
│   │   ├── analysis/        # GitHub 项目事实提取与简历一致性校验
│   │   ├── auth/            # 注册、登录、Session（Argon2 + HttpOnly Cookie）
│   │   ├── core/            # 配置、数据库连接、基础设施
│   │   ├── documents/       # 文档上传、解析、版本管理
│   │   ├── harness/         # LangGraph 状态机 + SSE 流式推送
│   │   ├── interviews/      # 模拟面试、动态追问、评分报告、能力记忆
│   │   ├── jobs/            # JD 录入、结构化抽取、能力差距分析
│   │   ├── mcp/             # MCP 客户端（GitHub、Calendar）+ JSON-RPC
│   │   ├── plans/           # 学习计划生成与任务管理
│   │   ├── rag/             # 百炼网关、Qdrant 索引、Dense+Sparse 检索
│   │   ├── skills/          # Skill 注册中心 + 6 个 Skill Manifest
│   │   ├── tools/           # Tool Registry + Policy Engine + 审批队列
│   │   ├── traces/          # Agent 执行轨迹记录
│   │   ├── workspaces/      # 工作空间 CRUD
│   │   └── main.py          # FastAPI 应用入口
│   ├── migrations/          # Alembic 数据库迁移
│   ├── tests/               # 测试用例
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── features/        # 按功能模块拆分的页面组件
│   │   │   ├── auth/        # 登录/注册
│   │   │   ├── workspaces/  # 工作空间管理
│   │   │   ├── documents/   # 知识库
│   │   │   ├── jobs/        # JD 分析
│   │   │   ├── interviews/  # 模拟面试
│   │   │   ├── plans/       # 学习计划
│   │   │   ├── traces/      # 运行轨迹
│   │   │   ├── skills/      # 技能中心
│   │   │   ├── tools/       # 工具中心
│   │   │   ├── github/      # GitHub 集成
│   │   │   └── analysis/    # 项目分析
│   │   ├── api.ts           # 共享 API 请求层
│   │   ├── types.ts         # 共享类型定义
│   │   └── App.tsx          # 根组件
│   ├── vite.config.ts
│   └── package.json
├── .env.example              # 环境变量模板
├── 开发文档.md               # 完整开发文档（中文）
└── README.md
```

---

## 检查与测试

```bash
# 后端测试
cd backend
uv run pytest                     # 运行测试
uv run ruff check .               # 代码检查

# RAG 评测基线
uv run python -m app.rag.evaluate

# 前端
cd frontend
npm run build                     # 生产构建
```

---

## 演示数据

运行演示数据脚本，一键填充演示账号和完整数据：

```bash
cd backend
uv run python -m app.scripts.demo_data
```

**生成内容：**

| 数据 | 数量 |
|------|------|
| 演示账号 | 1 个（demo@careerpilot.dev / demo123） |
| 工作空间 | 1 个 |
| 简历文档 | 2 份（已索引） |
| JD | 2 个（已分析） |
| 模拟面试 | 1 场（已完成） |
| 学习计划 | 1 个（进行中） |
| 能力记忆 | 若干条 |

> 脚本会先检查是否已存在演示数据，避免重复创建。如需重置，删除演示用户即可。

---

## RAG 评测基线

| 指标 | Dense | Hybrid | 提升 |
|------|-------|--------|------|
| Recall@5 | 0.9792 | 0.9861 | +0.0069 |
| Recall@10 | 1.0000 | 1.0000 | — |
| MRR | 0.8750 | 0.8785 | +0.0035 |
| P50 延迟 | 1.66 ms | 5.57 ms | — |
| P95 延迟 | 3.49 ms | 9.89 ms | — |

> 评测基于 24 条固定评测集，包含相似技术主题的干扰文本。

---

## 技术栈

### 后端

- **框架**: FastAPI (async)
- **Agent**: LangGraph (StateGraph + SSE)
- **数据库**: PostgreSQL 18 + SQLAlchemy 2.0 (async)
- **迁移**: Alembic
- **向量检索**: Qdrant Local (Dense + Sparse + RRF)
- **AI**: 百炼 DashScope (Qwen 3.7)
- **MCP**: JSON-RPC 2.0 over stdio

### 前端

- **框架**: React 19 + TypeScript 5.8
- **构建**: Vite 7
- **样式**: 纯 CSS（无第三方 UI 库）

### DevOps

- **代码检查**: Ruff
- **测试**: pytest
- **版本控制**: Git + GitHub

---

## 架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 架构模式 | 模块化单体 | 单开发者可维护，无微服务开销 |
| 向量数据库 | Qdrant | 本地零配置启动，原生支持 Hybrid Search |
| 事实来源 | PostgreSQL | 文档和业务数据以 PG 为准，向量仅可重建索引 |
| Agent 编排 | LangGraph | 受控状态图，支持条件路由、中断审批、持久化 |
| 事件推送 | SSE | 相比 WebSocket 更轻量，单向推送 Agent 事件 |
| 外部工具 | MCP | GitHub/Calendar 等独立边界通过 MCP 接入 |
| 写操作 | 强制审批 | 所有外部写操作需用户确认后执行 |

---

## License

MIT © Town1106
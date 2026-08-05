# CareerPilot

基于证据链的求职准备与面试训练智能助理。

当前已实现：

- FastAPI 健康检查。
- 邮箱注册、登录、退出和 HttpOnly Session。
- 用户工作空间创建、列表、重命名和删除。
- PDF、DOCX、TXT、Markdown 文档上传、SHA-256 去重、版本管理、切块和删除。
- 使用百炼 Qwen Embedding 与标准库 Sparse 表示将文档块写入本地 Qdrant，并支持失败重试。
- 基于工作空间隔离的 Dense + Sparse + RRF 混合检索、证据问答和原文引用。
- JD 结构化抽取、能力标准化、个人证据匹配、覆盖率、优先缺口和多岗位比较。
- 根据公司和岗位使用百炼联网搜索公开面经，保存经来源白名单校验的题库并缓存 7 天。
- 基于岗位缺口的可恢复模拟面试、动态追问、独立评分报告和可管理能力记忆。
- React 工作空间、知识库、岗位分析、模拟面试和能力记忆界面。

## 快速启动

### 1. 后端

    cd D:\codex-project\match
    conda activate careerpilot
    cd backend
    python -m uv sync
    python -m uv run --env-file ../.env alembic upgrade head
    python -m uv run --env-file ../.env uvicorn app.main:app --reload

根目录 `.env` 保存本机数据库连接信息，不会提交到 Git。未加载 `.env` 时使用本地 SQLite。

RAG 使用以下环境变量（参照 `.env.example`）：

    DASHSCOPE_API_KEY=你的百炼 API Key
    DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    DASHSCOPE_CHAT_MODEL=qwen3.7-plus
    DASHSCOPE_EMBEDDING_MODEL=qwen3.7-text-embedding
    DASHSCOPE_EMBEDDING_DIMENSIONS=1024
    RAG_RETRIEVAL_MODE=hybrid

开发环境的 Qdrant 使用嵌入式本地模式，数据保存在 `backend/data/qdrant`，无需手动建库。该模式只适合单个后端进程；需要多进程或部署时再切换到 Qdrant Server。

如需 PostgreSQL，安装 Docker 后在项目根目录执行：

    docker compose up -d postgres

复制 `.env.example` 为 `.env`，再按实际环境修改连接信息：

    Copy-Item .env.example .env

### 2. 前端

另开一个 PowerShell：

    cd D:\codex-project\match\frontend
    npm install
    npm run dev

打开 http://localhost:5173。

## 检查

后端：

    cd D:\codex-project\match\backend
    python -m uv run pytest
    python -m uv run ruff check .

Dense RAG 基线评测（读取根目录 `.env` 中的百炼配置）：

    python -m uv run --env-file ../.env python -m app.rag.evaluate

结果写入 `backend/evals/results/dense-hybrid-comparison.json`，同时报告 Dense、Hybrid 和差值。

从旧版 Dense Collection 升级后，在知识库页面点击一次“重建全部索引”，即可为已有文档补充 Sparse 索引。

前端：

    cd D:\codex-project\match\frontend
    npm run build

API 文档：http://127.0.0.1:8000/docs

健康检查：http://127.0.0.1:8000/api/v1/health

## 项目结构

- `backend/app/core`：配置、数据库连接和基础设施。
- `backend/app/auth`：账户、Session 与鉴权依赖。
- `backend/app/workspaces`：工作空间模型、校验和接口。
- `backend/app/documents`：文档模型、解析、存储和接口。
- `backend/app/jobs`：JD、能力、证据匹配、差距计算和多岗位比较。
- `backend/app/interviews`：面试状态机、动态追问、评分报告和能力记忆。
- `backend/app/rag`：百炼模型调用、Qdrant 索引、检索与引用问答。
- `frontend/src/features`：按 auth、workspaces、documents、jobs、interviews 拆分的页面功能。
- `frontend/src/api.ts`、`types.ts`：共享请求逻辑与类型。

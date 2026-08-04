# CareerPilot

基于证据链的求职准备与面试训练智能助理。

当前已实现：

- FastAPI 健康检查。
- 邮箱注册、登录、退出和 HttpOnly Session。
- 用户工作空间创建、列表、重命名和删除。
- React 工作空间界面。

## 快速启动

### 1. 后端

    cd D:\codex-project\match
    conda activate careerpilot
    cd backend
    python -m uv sync
    python -m uv run alembic upgrade head
    python -m uv run uvicorn app.main:app --reload

未配置 DATABASE_URL 时使用本地 SQLite，适合快速开发。

如需 PostgreSQL，安装 Docker 后在项目根目录执行：

    docker compose up -d postgres

再在启动后端的 PowerShell 中设置：

    $env:DATABASE_URL="postgresql+asyncpg://careerpilot:careerpilot@127.0.0.1:5433/careerpilot"
    python -m uv run alembic upgrade head
    python -m uv run uvicorn app.main:app --reload

### 2. 前端

另开一个 PowerShell：

    cd D:\codex-project\match\frontend
    pnpm install
    pnpm dev

打开 http://localhost:5173。

## 检查

后端：

    cd D:\codex-project\match\backend
    python -m uv run pytest
    python -m uv run ruff check .

前端：

    cd D:\codex-project\match\frontend
    pnpm build

API 文档：http://127.0.0.1:8000/docs

健康检查：http://127.0.0.1:8000/api/v1/health

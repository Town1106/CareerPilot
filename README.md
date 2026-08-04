# CareerPilot

基于证据链的求职准备与面试训练智能助理。

## 后端开发

进入项目并激活 Python 3.12 环境：

    cd D:\codex-project\match
    conda activate careerpilot
    cd backend

安装依赖：

    python -m uv sync

启动 API：

    python -m uv run uvicorn app.main:app --reload

健康检查：

    http://127.0.0.1:8000/api/v1/health

运行检查：

    python -m uv run pytest
    python -m uv run ruff check .


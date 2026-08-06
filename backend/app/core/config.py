import os
from pathlib import Path

# 加载 backend/.env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key, val)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./careerpilot.db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = 7
SESSION_COOKIE = "careerpilot_session"
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")
DASHSCOPE_CHAT_MODEL = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen3.7-plus")
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "qwen3.7-text-embedding")
DASHSCOPE_EMBEDDING_DIMENSIONS = int(os.getenv("DASHSCOPE_EMBEDDING_DIMENSIONS", "1024"))
RAG_TOP_K = 5
RAG_RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL_MODE", "hybrid").lower()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

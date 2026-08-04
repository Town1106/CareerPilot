import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./careerpilot.db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = 7
SESSION_COOKIE = "careerpilot_session"


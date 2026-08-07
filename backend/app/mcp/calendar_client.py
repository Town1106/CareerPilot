"""Calendar MCP 客户端 — 支持 Mock 本地存储和 MCP 协议模式。

Mock 模式：将日历事件存储为本地 JSON 文件，按用户隔离。
MCP 协议模式：通过 StdioMCPClient 连接 Calendar MCP Server。
"""

import json
import logging
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.core.config import CALENDAR_MCP_COMMAND
from app.mcp.client import MCPClient
from app.mcp.jsonrpc import MCPProtocolError, StdioMCPClient

logger = logging.getLogger(__name__)

MOCK_STORE = Path(__file__).resolve().parent.parent.parent / ".calendar_events.json"


def _load_store() -> dict[str, list[dict[str, Any]]]:
    if MOCK_STORE.exists():
        try:
            return json.loads(MOCK_STORE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_store(data: dict[str, list[dict[str, Any]]]) -> None:
    MOCK_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CalendarMCPClient(MCPClient):
    """Calendar MCP 客户端，优先使用 MCP 协议，回退到 Mock 本地存储。"""

    def __init__(self) -> None:
        super().__init__()
        self._mcp: StdioMCPClient | None = None
        self._use_mcp = bool(CALENDAR_MCP_COMMAND)
        self._mock_events: dict[str, list[dict[str, Any]]] = {}
        self._owner_user_id: str | None = None

    async def connect(self, user_id: str | None = None) -> None:
        if self._connected:
            if self._mcp:
                self._require_mcp_owner(user_id or "")
            return
        if self._use_mcp:
            try:
                cmd = CALENDAR_MCP_COMMAND.split()
                self._mcp = StdioMCPClient(cmd)
                await self._mcp.connect()
                self._connected = True
                self._owner_user_id = user_id
                logger.info("Calendar MCP protocol connected, %d tools available", len(self._mcp.tools))
                return
            except (MCPProtocolError, FileNotFoundError, OSError, NotImplementedError) as e:
                logger.warning("Calendar MCP protocol failed (%s), falling back to Mock", e)
                self._mcp = None
                self._use_mcp = False
        # Mock 回退
        self._mock_events = _load_store()
        self._connected = True
        logger.info("Calendar Mock mode connected")

    async def disconnect(self) -> None:
        if self._mcp:
            await self._mcp.disconnect()
            self._mcp = None
        self._connected = False
        self._owner_user_id = None

    def _require_mcp_owner(self, user_id: str) -> None:
        if self._mcp and self._owner_user_id != user_id:
            raise PermissionError("Calendar 连接属于其他用户")

    def require_owner(self, user_id: str) -> None:
        self._require_mcp_owner(user_id)

    async def create_event(
        self,
        user_id: str,
        title: str,
        description: str,
        event_date: date,
        duration_minutes: int,
        source_task_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_mcp_owner(user_id)
        if self._mcp:
            result = await self._mcp.call_tool("create_event", {
                "title": title,
                "description": description,
                "date": event_date.isoformat(),
                "duration_minutes": duration_minutes,
            })
            return result if isinstance(result, dict) else {}

        # Mock mode
        event_id = str(uuid.uuid4())
        event = {
            "id": event_id,
            "title": title,
            "description": description,
            "date": event_date.isoformat(),
            "duration_minutes": duration_minutes,
            "source_task_id": source_task_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        events = self._mock_events.setdefault(user_id, [])
        events.append(event)
        _save_store(self._mock_events)
        return event

    async def list_events(self, user_id: str) -> list[dict[str, Any]]:
        self._require_mcp_owner(user_id)
        if self._mcp:
            result = await self._mcp.call_tool("list_events", {})
            return result if isinstance(result, list) else []

        return self._mock_events.get(user_id, [])

    async def delete_event(self, user_id: str, event_id: str) -> bool:
        self._require_mcp_owner(user_id)
        if self._mcp:
            await self._mcp.call_tool("delete_event", {"event_id": event_id})
            return True

        events = self._mock_events.get(user_id, [])
        for i, ev in enumerate(events):
            if ev["id"] == event_id:
                events.pop(i)
                _save_store(self._mock_events)
                return True
        return False


_calendar_client: CalendarMCPClient | None = None


def get_calendar_client() -> CalendarMCPClient:
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = CalendarMCPClient()
    return _calendar_client

"""MCP JSON-RPC 2.0 客户端，通过 stdio 与 MCP Server 通信。

支持标准 MCP 协议的生命周期：
  initialize → initialized → (tools/list, tools/call)* → disconnect
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


class MCPProtocolError(Exception):
    """MCP 协议层错误。"""


class StdioMCPClient:
    """通过子进程 stdio 与 MCP Server 通信的 JSON-RPC 客户端。"""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._connected = False
        self._server_info: dict[str, Any] = {}
        self._tools: list[dict[str, Any]] = []

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if sys.platform == "win32":
            # Windows: npx/npm are .cmd files, need shell mode
            cmd = subprocess.list2cmdline(self._command)
            self._process = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **(self._env or {})},
            )
        else:
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **(self._env or {})},
            )
        try:
            result = await self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "CareerPilot", "version": "0.1.0"},
            })
            self._server_info = result
            await self._send("notifications/initialized", {})
            self._connected = True
            logger.info("MCP connected: %s", self._server_info.get("serverInfo", {}).get("name", "unknown"))
        except Exception:
            await self._cleanup()
            raise

        tools_result = await self._request("tools/list", {})
        self._tools = tools_result.get("tools", [])
        logger.info("MCP discovered %d tools", len(self._tools))

    async def disconnect(self) -> None:
        self._connected = False
        await self._cleanup()

    async def _cleanup(self) -> None:
        if self._process:
            try:
                self._process.stdin.close()
            except OSError:
                logger.debug("stdin close failed", exc_info=True)
            try:
                self._process.kill()
            except OSError:
                logger.debug("process kill failed", exc_info=True)
            await self._process.wait()
            self._process = None

    @property
    def tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        if isinstance(content, list) and len(content) == 1:
            item = content[0]
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except (json.JSONDecodeError, TypeError):
                    return item["text"]
        return content

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        if not self._process or self._process.stdin is None or self._process.stdout is None:
            raise MCPProtocolError("MCP client not connected")
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        payload = json.dumps(request, ensure_ascii=False) + "\n"
        self._process.stdin.write(payload.encode("utf-8"))
        await self._process.stdin.drain()

        line = await asyncio.wait_for(self._process.stdout.readline(), timeout=30.0)
        if not line:
            raise MCPProtocolError("MCP server closed connection")
        try:
            response = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise MCPProtocolError(f"Invalid JSON-RPC response: {e}") from e

        if "error" in response:
            err = response["error"]
            raise MCPProtocolError(f"MCP error {err.get('code')}: {err.get('message', 'unknown')}")
        if response.get("id") != request["id"]:
            raise MCPProtocolError(f"Response id mismatch: expected {request['id']}, got {response.get('id')}")
        return response.get("result", {})

    async def _send(self, method: str, params: dict[str, Any]) -> None:
        if not self._process or self._process.stdin is None:
            return
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        payload = json.dumps(notification, ensure_ascii=False) + "\n"
        self._process.stdin.write(payload.encode("utf-8"))
        await self._process.stdin.drain()
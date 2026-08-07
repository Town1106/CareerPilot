import logging
from typing import Any

import httpx

from app.core.config import GITHUB_MCP_COMMAND, GITHUB_TOKEN
from app.mcp.client import MCPClient
from app.mcp.jsonrpc import MCPProtocolError, StdioMCPClient

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubHTTPClient:
    """GitHub REST API 直连模式（回退方案）。"""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if not GITHUB_TOKEN:
            self._connected = False
            return
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CareerPilot",
            },
            timeout=15.0,
        )
        resp = await self._client.get("/user")
        if resp.status_code == 200:
            self._connected = True
            logger.info("GitHub HTTP connected as %s", resp.json().get("login"))
        else:
            self._connected = False
            logger.warning("GitHub HTTP auth failed: %s", resp.status_code)
            await self._client.aclose()
            self._client = None

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def _get(self, path: str, **params: Any) -> dict[str, Any] | list[Any]:
        if not self._client or not self._connected:
            raise RuntimeError("GitHub not connected")
        resp = await self._client.get(path, params=params or None)
        if resp.status_code >= 400:
            data = resp.json()
            raise RuntimeError(f"GitHub API error {resp.status_code}: {data.get('message', '')}")
        return resp.json()

    async def list_repos(self, page: int = 1, per_page: int = 30) -> tuple[list[dict[str, Any]], bool]:
        data = await self._get("/user/repos", sort="updated", page=page, per_page=per_page)
        repos = data if isinstance(data, list) else []
        return repos, len(repos) == per_page

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        data = await self._get(f"/repos/{owner}/{repo}")
        return data if isinstance(data, dict) else {}

    async def get_readme(self, owner: str, repo: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}/readme")
        if isinstance(data, dict):
            return data.get("content", "")
        return ""

    async def list_commits(self, owner: str, repo: str, per_page: int = 10) -> list[dict[str, Any]]:
        data = await self._get(f"/repos/{owner}/{repo}/commits", per_page=per_page)
        return data if isinstance(data, list) else []

    async def get_file_content(self, owner: str, repo: str, path: str) -> dict[str, Any]:
        data = await self._get(f"/repos/{owner}/{repo}/contents/{path}")
        return data if isinstance(data, dict) else {}

    async def search_repos(self, query: str, page: int = 1, per_page: int = 30) -> tuple[list[dict[str, Any]], bool]:
        data = await self._get("/search/repositories", q=query, page=page, per_page=per_page)
        items = data.get("items", []) if isinstance(data, dict) else []
        return items, len(items) == per_page


class GitHubMCPClient(MCPClient):
    """GitHub MCP 客户端，优先使用标准 MCP 协议，回退到 HTTP 直连。

    通过 MCP 协议时，连接一个 GitHub MCP Server 子进程（如
    ``npx @modelcontextprotocol/server-github``），通过 JSON-RPC over stdio 通信。
    服务器启动时会自动读取 GITHUB_TOKEN 环境变量进行认证。
    """

    def __init__(self) -> None:
        super().__init__()
        self._mcp: StdioMCPClient | None = None
        self._http: GitHubHTTPClient | None = None
        self._use_mcp = bool(GITHUB_MCP_COMMAND)
        self._owner_user_id: str | None = None

    async def connect(self, user_id: str | None = None) -> None:
        if self._connected:
            self.require_owner(user_id)
            return
        if self._use_mcp:
            try:
                cmd = GITHUB_MCP_COMMAND.split()
                self._mcp = StdioMCPClient(cmd, env={"GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN})
                await self._mcp.connect()
                self._connected = True
                self._owner_user_id = user_id
                logger.info("GitHub MCP protocol connected, %d tools available", len(self._mcp.tools))
                return
            except (MCPProtocolError, FileNotFoundError, OSError, NotImplementedError) as e:
                logger.warning("MCP protocol failed (%s), falling back to HTTP", e)
                self._mcp = None
                self._use_mcp = False
        # HTTP 回退
        self._http = GitHubHTTPClient()
        await self._http.connect()
        self._connected = self._http.connected
        self._owner_user_id = user_id if self._connected else None

    async def disconnect(self) -> None:
        if self._mcp:
            await self._mcp.disconnect()
            self._mcp = None
        if self._http:
            await self._http.disconnect()
            self._http = None
        self._connected = False
        self._owner_user_id = None

    def require_owner(self, user_id: str | None) -> None:
        if self._connected and self._owner_user_id != user_id:
            raise PermissionError("GitHub 连接属于其他用户")

    async def list_repos(self, page: int = 1, per_page: int = 30) -> tuple[list[dict[str, Any]], bool]:
        if self._mcp:
            result = await self._mcp.call_tool("list_repositories", {})
            if isinstance(result, list):
                return result, len(result) == per_page
            repos = result.get("repositories", []) if isinstance(result, dict) else []
            return repos, len(repos) == per_page
        if self._http:
            return await self._http.list_repos(page, per_page)
        return [], False

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        if self._mcp:
            result = await self._mcp.call_tool("get_repository", {"owner": owner, "repo": repo})
            return result if isinstance(result, dict) else {}
        if self._http:
            return await self._http.get_repo(owner, repo)
        return {}

    async def get_readme(self, owner: str, repo: str) -> str:
        if self._mcp:
            try:
                result = await self._mcp.call_tool("get_file_contents", {
                    "owner": owner, "repo": repo, "path": "README.md",
                })
                if isinstance(result, dict):
                    return result.get("content", "")
            except MCPProtocolError:
                pass
        if self._http:
            return await self._http.get_readme(owner, repo)
        return ""

    async def list_commits(self, owner: str, repo: str, per_page: int = 10) -> list[dict[str, Any]]:
        if self._mcp:
            result = await self._mcp.call_tool("list_commits", {"owner": owner, "repo": repo})
            return result if isinstance(result, list) else []
        if self._http:
            return await self._http.list_commits(owner, repo, per_page)
        return []

    async def get_file_content(self, owner: str, repo: str, path: str) -> dict[str, Any]:
        if self._mcp:
            try:
                result = await self._mcp.call_tool("get_file_contents", {
                    "owner": owner, "repo": repo, "path": path,
                })
                return result if isinstance(result, dict) else {}
            except MCPProtocolError:
                pass
        if self._http:
            return await self._http.get_file_content(owner, repo, path)
        return {}

    async def search_repos(self, query: str, page: int = 1, per_page: int = 30) -> tuple[list[dict[str, Any]], bool]:
        if self._mcp:
            result = await self._mcp.call_tool("search_repositories", {"query": query})
            items = result if isinstance(result, list) else result.get("items", []) if isinstance(result, dict) else []
            return items, len(items) == per_page
        if self._http:
            return await self._http.search_repos(query, page, per_page)
        return [], False


_github_client: GitHubMCPClient | None = None


def get_github_client() -> GitHubMCPClient:
    global _github_client
    if _github_client is None:
        _github_client = GitHubMCPClient()
    return _github_client

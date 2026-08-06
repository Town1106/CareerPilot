import logging
from typing import Any

import httpx

from app.core.config import GITHUB_TOKEN
from app.mcp.client import MCPClient

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubMCPClient(MCPClient):
    """GitHub 只读 MCP 客户端，封装 GitHub REST API。"""

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None

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
            logger.info("GitHub MCP connected as %s", resp.json().get("login"))
        else:
            self._connected = False
            logger.warning("GitHub MCP auth failed: %s", resp.status_code)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def _get(self, path: str, **params: Any) -> dict[str, Any] | list[Any]:
        if not self._client or not self._connected:
            raise RuntimeError("GitHub MCP not connected")
        resp = await self._client.get(path, params=params or None)
        if resp.status_code >= 400:
            data = resp.json()
            raise RuntimeError(f"GitHub API error {resp.status_code}: {data.get('message', '')}")
        return resp.json()

    async def list_repos(self, page: int = 1, per_page: int = 30) -> tuple[list[dict[str, Any]], bool]:
        """列出当前用户仓库，返回 (列表, 是否还有下一页)。"""
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


_github_client: GitHubMCPClient | None = None


def get_github_client() -> GitHubMCPClient:
    global _github_client
    if _github_client is None:
        _github_client = GitHubMCPClient()
    return _github_client
import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import current_user
from app.auth.models import User
from app.mcp.github_client import get_github_client
from app.mcp.schemas import (
    CommitItem,
    CommitList,
    FileContent,
    MCPStatus,
    RepoDetail,
    RepoList,
    RepoSummary,
)

router = APIRouter(tags=["mcp"])
logger = logging.getLogger(__name__)


_active = False


@router.post("/api/v1/mcp/github/connect", response_model=MCPStatus)
async def connect_github(user: User = Depends(current_user)) -> MCPStatus:
    global _active
    client = get_github_client()
    try:
        await client.connect()
        if client.connected:
            _active = True
            return MCPStatus(provider="github", connected=True, message="GitHub 连接成功")
        return MCPStatus(provider="github", connected=False, message="GitHub Token 无效或未配置")
    except Exception as e:
        logger.exception("GitHub connect failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitHub 连接失败: {e}") from e


@router.post("/api/v1/mcp/github/disconnect", response_model=MCPStatus)
async def disconnect_github(user: User = Depends(current_user)) -> MCPStatus:
    global _active
    client = get_github_client()
    await client.disconnect()
    _active = False
    return MCPStatus(provider="github", connected=False, message="GitHub 已断开")


@router.get("/api/v1/mcp/github/repos", response_model=RepoList)
async def list_repos(
    page: int = Query(1, ge=1),
    user: User = Depends(current_user),
) -> RepoList:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    items, _ = await client.list_repos(page=page)
    return RepoList(
        repos=[
            RepoSummary(
                name=r["name"],
                full_name=r["full_name"],
                description=r.get("description"),
                language=r.get("language"),
                stargazers_count=r.get("stargazers_count", 0),
                updated_at=r.get("updated_at", ""),
                html_url=r.get("html_url", ""),
            )
            for r in items
        ]
    )


@router.get("/api/v1/mcp/github/repos/{owner}/{repo:path}", response_model=RepoDetail)
async def get_repo(
    owner: str,
    repo: str,
    user: User = Depends(current_user),
) -> RepoDetail:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    data = await client.get_repo(owner, repo)
    return RepoDetail(
        name=data["name"],
        full_name=data["full_name"],
        description=data.get("description"),
        language=data.get("language"),
        stargazers_count=data.get("stargazers_count", 0),
        updated_at=data.get("updated_at", ""),
        html_url=data.get("html_url", ""),
        topics=data.get("topics", []),
        default_branch=data.get("default_branch", "main"),
        open_issues_count=data.get("open_issues_count", 0),
        created_at=data.get("created_at", ""),
    )


@router.get("/api/v1/mcp/github/repos/{owner}/{repo:path}/readme")
async def get_readme(
    owner: str,
    repo: str,
    user: User = Depends(current_user),
) -> dict[str, str]:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    b64 = await client.get_readme(owner, repo)
    if not b64:
        return {"content": ""}
    try:
        return {"content": base64.b64decode(b64).decode("utf-8", errors="replace")}
    except (ValueError, UnicodeDecodeError):
        return {"content": b64}


@router.get("/api/v1/mcp/github/repos/{owner}/{repo:path}/commits", response_model=CommitList)
async def list_commits(
    owner: str,
    repo: str,
    per_page: int = Query(10, ge=1, le=50),
    user: User = Depends(current_user),
) -> CommitList:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    items = await client.list_commits(owner, repo, per_page=per_page)
    return CommitList(
        commits=[
            CommitItem(
                sha=c["sha"],
                message=c["commit"]["message"].split("\n")[0] if "commit" in c else "",
                author=c["commit"]["author"]["name"] if "commit" in c else "",
                date=c["commit"]["author"]["date"] if "commit" in c else "",
            )
            for c in items
        ]
    )


@router.get("/api/v1/mcp/github/repos/{owner}/{repo:path}/files/{path:path}")
async def get_file(
    owner: str,
    repo: str,
    path: str,
    user: User = Depends(current_user),
) -> FileContent:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    data = await client.get_file_content(owner, repo, path)
    if isinstance(data, list):
        return FileContent(path=path, content="", size=0)
    raw = data.get("content", "")
    size = data.get("size", 0)
    try:
        content = base64.b64decode(raw).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        content = raw
    return FileContent(path=path, content=content, size=size)
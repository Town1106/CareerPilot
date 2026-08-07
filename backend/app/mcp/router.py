import base64
import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.config import DASHSCOPE_API_KEY
from app.core.database import get_db
from app.documents import files
from app.documents.models import Document, DocumentChunk, DocumentVersion
from app.mcp.calendar_client import get_calendar_client
from app.mcp.github_client import get_github_client
from app.mcp.schemas import (
    CalendarEventCreate,
    CalendarEventOut,
    CommitItem,
    CommitList,
    FileContent,
    ImportRequest,
    MCPStatus,
    RepoDetail,
    RepoList,
    RepoSummary,
)
from app.rag.service import index_document
from app.tools.service import ToolApprovalRequired, authorize_tool, mark_tool_executed
from app.workspaces.dependencies import owned_workspace
from app.workspaces.models import Workspace

router = APIRouter(tags=["mcp"])
logger = logging.getLogger(__name__)


_active = False


def _github_for(user: User):
    client = get_github_client()
    try:
        client.require_owner(str(user.id))
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    return client


def _calendar_for(user: User):
    client = get_calendar_client()
    try:
        client.require_owner(str(user.id))
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    return client


@router.post("/api/v1/mcp/github/connect", response_model=MCPStatus)
async def connect_github(user: User = Depends(current_user)) -> MCPStatus:
    global _active
    client = get_github_client()
    try:
        await client.connect(str(user.id))
        if client.connected:
            _active = True
            return MCPStatus(provider="github", connected=True, message="GitHub 连接成功")
        return MCPStatus(provider="github", connected=False, message="GitHub Token 无效或未配置")
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except Exception as e:
        logger.exception("GitHub connect failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitHub 连接失败: {e}") from e


@router.post("/api/v1/mcp/github/disconnect", response_model=MCPStatus)
async def disconnect_github(user: User = Depends(current_user)) -> MCPStatus:
    global _active
    client = _github_for(user)
    await client.disconnect()
    _active = False
    return MCPStatus(provider="github", connected=False, message="GitHub 已断开")


@router.get("/api/v1/mcp/github/repos", response_model=RepoList)
async def list_repos(
    page: int = Query(1, ge=1),
    user: User = Depends(current_user),
) -> RepoList:
    client = _github_for(user)
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


@router.get("/api/v1/mcp/github/repos/{owner}/{repo}", response_model=RepoDetail)
async def get_repo(
    owner: str,
    repo: str,
    user: User = Depends(current_user),
) -> RepoDetail:
    client = _github_for(user)
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


@router.get("/api/v1/mcp/github/repos/{owner}/{repo}/readme")
async def get_readme(
    owner: str,
    repo: str,
    user: User = Depends(current_user),
) -> dict[str, str]:
    client = _github_for(user)
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    b64 = await client.get_readme(owner, repo)
    if not b64:
        return {"content": ""}
    try:
        return {"content": base64.b64decode(b64).decode("utf-8", errors="replace")}
    except (ValueError, UnicodeDecodeError):
        return {"content": b64}


@router.get("/api/v1/mcp/github/repos/{owner}/{repo}/commits", response_model=CommitList)
async def list_commits(
    owner: str,
    repo: str,
    per_page: int = Query(10, ge=1, le=50),
    user: User = Depends(current_user),
) -> CommitList:
    client = _github_for(user)
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


async def _import_readme(
    db: AsyncSession, workspace_id, owner: str, repo: str
) -> dict:
    client = get_github_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub 未连接")
    b64 = await client.get_readme(owner, repo)
    if not b64:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该仓库没有 README")
    try:
        text = base64.b64decode(b64).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "无法解码 README")

    content = text.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()

    duplicate = (
        await db.execute(
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(Document.workspace_id == workspace_id, DocumentVersion.sha256 == digest)
            .limit(1)
        )
    ).first()
    if duplicate:
        return {"imported": False, "message": "README 已存在于知识库中"}

    original_name = f"{owner}/{repo}.md"
    chunks = files.make_chunks([(None, text)])

    document = Document(
        workspace_id=workspace_id,
        original_name=original_name,
        category="project",
    )
    db.add(document)
    await db.flush()

    stored_name = files.save_file(".md", content)
    version = DocumentVersion(
        document_id=document.id,
        version=1,
        original_name=original_name,
        stored_name=stored_name,
        media_type="text/markdown",
        size_bytes=len(content),
        sha256=digest,
        status="parsed",
        chunk_count=len(chunks),
    )
    db.add(version)
    await db.flush()

    db.add_all(
        DocumentChunk(
            version_id=version.id,
            position=idx,
            page_number=None,
            content=chunk_text,
        )
        for idx, (_, chunk_text) in enumerate(chunks)
    )
    document.original_name = original_name
    document.active_version_id = version.id
    await db.commit()
    await db.refresh(document)
    await db.refresh(version)

    if DASHSCOPE_API_KEY:
        version = await index_document(db, document, version)

    return {
        "imported": True,
        "document_id": str(document.id),
        "version_id": str(version.id),
        "name": original_name,
        "chunks": len(chunks),
        "status": version.status,
    }


@router.post("/api/v1/mcp/github/import")
async def import_to_workspace(
    body: ImportRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    user_confirmed: bool = Header(False, alias="X-User-Confirmed"),
    approval_id: uuid.UUID | None = Header(None, alias="X-Tool-Approval"),
) -> dict:
    await owned_workspace(body.workspace_id, user, db)
    _github_for(user)
    try:
        approval = await authorize_tool(
            db,
            body.workspace_id,
            "document-upload",
            body.model_dump(mode="json"),
            user_confirmed=user_confirmed,
            approval_id=approval_id,
        )
    except ToolApprovalRequired as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "approval_required", "approval_id": str(error.approval_id)},
        ) from None
    except RuntimeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    owner, repo = body.repo_full_name.split("/", 1)
    result = await _import_readme(db, body.workspace_id, owner, repo)
    await mark_tool_executed(db, approval)
    return result


@router.post("/api/v1/mcp/github/repos/{owner}/{repo}/import")
async def import_readme(
    owner: str,
    repo: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    user_confirmed: bool = Header(False, alias="X-User-Confirmed"),
    approval_id: uuid.UUID | None = Header(None, alias="X-Tool-Approval"),
) -> dict:
    ws = await db.scalar(select(Workspace).where(Workspace.user_id == user.id).limit(1))
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    _github_for(user)
    try:
        approval = await authorize_tool(
            db,
            ws.id,
            "document-upload",
            {"workspace_id": str(ws.id), "repo_full_name": f"{owner}/{repo}"},
            user_confirmed=user_confirmed,
            approval_id=approval_id,
        )
    except ToolApprovalRequired as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "approval_required", "approval_id": str(error.approval_id)},
        ) from None
    except RuntimeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    result = await _import_readme(db, ws.id, owner, repo)
    await mark_tool_executed(db, approval)
    return result


@router.get("/api/v1/mcp/github/repos/{owner}/{repo}/files/{path:path}")
async def get_file(
    owner: str,
    repo: str,
    path: str,
    user: User = Depends(current_user),
) -> FileContent:
    client = _github_for(user)
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


# ── Calendar MCP ──

_calendar_active = False


@router.post("/api/v1/mcp/calendar/connect", response_model=MCPStatus)
async def connect_calendar(user: User = Depends(current_user)) -> MCPStatus:
    global _calendar_active
    client = get_calendar_client()
    try:
        await client.connect(str(user.id))
        if client.connected:
            _calendar_active = True
            return MCPStatus(provider="calendar", connected=True, message="Calendar 连接成功")
        return MCPStatus(provider="calendar", connected=False, message="Calendar 不可用")
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except Exception as e:
        logger.exception("Calendar connect failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Calendar 连接失败: {e}") from e


@router.post("/api/v1/mcp/calendar/disconnect", response_model=MCPStatus)
async def disconnect_calendar(user: User = Depends(current_user)) -> MCPStatus:
    global _calendar_active
    client = _calendar_for(user)
    await client.disconnect()
    _calendar_active = False
    return MCPStatus(provider="calendar", connected=False, message="Calendar 已断开")


@router.post("/api/v1/mcp/calendar/events", response_model=CalendarEventOut)
async def create_calendar_event(
    payload: CalendarEventCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    user_confirmed: bool = Header(False, alias="X-User-Confirmed"),
    approval_id: uuid.UUID | None = Header(None, alias="X-Tool-Approval"),
) -> CalendarEventOut:
    await owned_workspace(payload.workspace_id, user, db)
    try:
        approval = await authorize_tool(
            db,
            payload.workspace_id,
            "calendar-event-create",
            payload.model_dump(mode="json"),
            user_confirmed=user_confirmed,
            approval_id=approval_id,
        )
    except ToolApprovalRequired as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "approval_required", "approval_id": str(error.approval_id)},
        ) from None
    except RuntimeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    client = get_calendar_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Calendar 未连接")
    event = await client.create_event(
        user_id=str(user.id),
        title=payload.title,
        description=payload.description,
        event_date=payload.date,
        duration_minutes=payload.duration_minutes,
        source_task_id=payload.source_task_id,
    )
    await mark_tool_executed(db, approval)
    return CalendarEventOut(**event)


@router.get("/api/v1/mcp/calendar/events", response_model=list[CalendarEventOut])
async def list_calendar_events(
    user: User = Depends(current_user),
) -> list[CalendarEventOut]:
    client = get_calendar_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Calendar 未连接")
    events = await client.list_events(str(user.id))
    return [CalendarEventOut(**ev) for ev in events]


@router.delete("/api/v1/mcp/calendar/events/{event_id}")
async def delete_calendar_event(
    event_id: str,
    workspace_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    user_confirmed: bool = Header(False, alias="X-User-Confirmed"),
    approval_id: uuid.UUID | None = Header(None, alias="X-Tool-Approval"),
) -> dict[str, bool]:
    await owned_workspace(workspace_id, user, db)
    try:
        approval = await authorize_tool(
            db,
            workspace_id,
            "calendar-event-delete",
            {"event_id": event_id},
            user_confirmed=user_confirmed,
            approval_id=approval_id,
        )
    except ToolApprovalRequired as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "approval_required", "approval_id": str(error.approval_id)},
        ) from None
    except RuntimeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    client = get_calendar_client()
    if not client.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Calendar 未连接")
    deleted = await client.delete_event(str(user.id), event_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "事件不存在")
    await mark_tool_executed(db, approval)
    return {"deleted": True}

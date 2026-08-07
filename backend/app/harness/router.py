"""Agent Harness API 路由 — SSE 流式端点。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.harness.stream import stream_agent
from app.workspaces.dependencies import owned_workspace

router = APIRouter(tags=["harness"])


class AgentStreamRequest(BaseModel):
    skill_name: str
    input: dict


@router.post("/api/v1/workspaces/{workspace_id}/agent/stream")
async def agent_stream(
    workspace_id: uuid.UUID,
    payload: AgentStreamRequest,
    user: User = Depends(current_user),  # noqa: B008 — FastAPI Depends pattern
    db: AsyncSession = Depends(get_db),  # noqa: B008 — FastAPI Depends pattern
) -> StreamingResponse:
    """LangGraph Agent SSE 流式端点。

    支持 skill_name: ``rag_qa``, ``jd_analysis``。
    """
    if payload.skill_name not in ("rag_qa", "jd_analysis", "study_plan"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的 Skill: {payload.skill_name}")
    await owned_workspace(workspace_id, user, db)

    return StreamingResponse(
        stream_agent(
            skill_name=payload.skill_name,
            workspace_id=str(workspace_id),
            user_id=str(user.id),
            input_data=payload.input,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

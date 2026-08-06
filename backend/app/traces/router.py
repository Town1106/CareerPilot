import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db
from app.traces.models import AgentRun
from app.traces.schemas import RunDetailOut, RunListOut
from app.traces.service import get_run_detail, list_runs
from app.workspaces.dependencies import owned_workspace

router = APIRouter(tags=["traces"])


@router.get(
    "/api/v1/workspaces/{workspace_id}/runs",
    response_model=RunListOut,
)
async def workspace_runs(
    workspace_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> RunListOut:
    await owned_workspace(workspace_id, user, db)
    return await list_runs(db, workspace_id, limit=limit, offset=offset)


@router.get(
    "/api/v1/runs/{run_id}",
    response_model=RunDetailOut,
)
async def run_detail(
    run_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> RunDetailOut:
    run = await db.scalar(select(AgentRun).where(AgentRun.id == run_id))
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    await owned_workspace(run.workspace_id, user, db)
    return await get_run_detail(db, run)
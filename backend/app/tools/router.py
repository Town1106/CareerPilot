import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.core.database import get_db, utc_now
from app.tools.models import ToolApproval, ToolDefinition, ToolPolicy
from app.tools.schemas import (
    ApprovalListOut,
    ApprovalOut,
    ToolApproveIn,
    ToolDetailOut,
    ToolListOut,
    ToolOut,
)
from app.workspaces.models import Workspace

router = APIRouter(tags=["tools"])


@router.get("/api/v1/tools", response_model=ToolListOut)
async def list_tools(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ToolListOut:
    rows = list((await db.scalars(select(ToolDefinition).order_by(ToolDefinition.name))).all())
    return ToolListOut(tools=[ToolOut.model_validate(r) for r in rows])


@router.get("/api/v1/tools/{name}", response_model=ToolDetailOut)
async def get_tool(
    name: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ToolDetailOut:
    row = await db.scalar(select(ToolDefinition).where(ToolDefinition.name == name))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tool not found")
    policy = await db.scalar(select(ToolPolicy).where(ToolPolicy.tool_name == name))
    return ToolDetailOut(
        id=row.id,
        name=row.name,
        version=row.version,
        description=row.description,
        manifest_path=row.manifest_path,
        risk_level=row.risk_level,
        status=row.status,
        created_at=row.created_at,
        input_schema=row.input_schema,
        output_schema=row.output_schema,
        require_approval=policy.require_approval if policy else False,
        approval_prompt=policy.approval_prompt if policy else None,
        max_per_session=policy.max_per_session if policy else None,
    )


@router.get("/api/v1/tools/approvals/pending", response_model=ApprovalListOut)
async def list_pending_approvals(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalListOut:
    ws = await db.scalar(select(Workspace).where(Workspace.user_id == user.id).limit(1))
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    rows = list(
        (
            await db.scalars(
                select(ToolApproval)
                .where(ToolApproval.workspace_id == ws.id)
                .where(ToolApproval.status == "pending")
                .order_by(ToolApproval.created_at.desc())
            )
        ).all()
    )
    return ApprovalListOut(approvals=[ApprovalOut.model_validate(r) for r in rows])


@router.post("/api/v1/tools/approvals/{approval_id}/decide", response_model=ApprovalOut)
async def decide_approval(
    approval_id: uuid.UUID,
    body: ToolApproveIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    row = await db.scalar(select(ToolApproval).where(ToolApproval.id == approval_id))
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval not found")
    if row.status != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Approval already decided")
    row.status = "approved" if body.approve else "denied"
    row.decided_at = utc_now()
    await db.flush()
    return ApprovalOut.model_validate(row)
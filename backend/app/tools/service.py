import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utc_now
from app.tools.models import ToolApproval, ToolPolicy


class ToolApprovalRequired(RuntimeError):
    def __init__(self, approval_id: uuid.UUID):
        super().__init__("工具调用需要用户审批")
        self.approval_id = approval_id


async def authorize_tool(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    tool_name: str,
    payload: dict,
    *,
    user_confirmed: bool,
    approval_id: uuid.UUID | None = None,
) -> ToolApproval | None:
    policy = await db.scalar(select(ToolPolicy).where(ToolPolicy.tool_name == tool_name))
    if policy is None:
        raise RuntimeError(f"工具策略不存在：{tool_name}")
    if not policy.require_approval:
        return None
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    if approval_id:
        approval = await db.scalar(
            select(ToolApproval).where(
                ToolApproval.id == approval_id,
                ToolApproval.workspace_id == workspace_id,
                ToolApproval.tool_name == tool_name,
                ToolApproval.status == "approved",
                ToolApproval.payload_summary.startswith(f"sha256:{digest}"),
            )
        )
        if not approval:
            raise RuntimeError("审批不存在、未通过或与本次调用不匹配")
        return approval
    approval = ToolApproval(
        workspace_id=workspace_id,
        tool_name=tool_name,
        payload_summary=f"sha256:{digest} | {encoded[:420]}",
        status="approved" if user_confirmed else "pending",
        decided_at=utc_now() if user_confirmed else None,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    if not user_confirmed:
        raise ToolApprovalRequired(approval.id)
    return approval


async def mark_tool_executed(db: AsyncSession, approval: ToolApproval | None) -> None:
    if approval:
        approval.status = "executed"
        await db.commit()

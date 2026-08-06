import uuid
from datetime import datetime

from pydantic import BaseModel


class ToolOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    manifest_path: str
    risk_level: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolDetailOut(ToolOut):
    input_schema: str | None
    output_schema: str | None
    require_approval: bool
    approval_prompt: str | None
    max_per_session: int | None


class ToolListOut(BaseModel):
    tools: list[ToolOut]


class ToolApproveIn(BaseModel):
    approve: bool


class ApprovalOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    tool_name: str
    run_id: uuid.UUID | None
    requested_by_skill: str | None
    payload_summary: str
    status: str
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalListOut(BaseModel):
    approvals: list[ApprovalOut]
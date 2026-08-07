import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FactOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    repo_full_name: str
    extracted_tech_stack: list[str] | None
    extracted_summary: str | None
    extracted_role: str | None
    commit_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FactListOut(BaseModel):
    facts: list[FactOut]


class ReportOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    repo_full_name: str
    matched_items: list[dict] | None
    missing_in_resume: list[dict] | None
    conflicts: list[dict] | None
    overall_score: float = Field(ge=0, le=100)
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListOut(BaseModel):
    reports: list[ReportOut]


class ExtractRequest(BaseModel):
    repo_full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")


class CheckRequest(BaseModel):
    repo_full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")

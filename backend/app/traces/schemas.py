import uuid
from datetime import datetime

from pydantic import BaseModel


class RunOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    run_type: str
    status: str
    model_id: str | None
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    error_code: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class StepOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_name: str
    status: str
    input_summary: str | None
    output_summary: str | None
    retrieved_chunks: str | None
    latency_ms: int
    error_code: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RunDetailOut(RunOut):
    steps: list[StepOut]


class RunListOut(BaseModel):
    runs: list[RunOut]
    total: int
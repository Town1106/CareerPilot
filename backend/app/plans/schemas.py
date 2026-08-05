import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskStatus = str


class PlanGenerate(BaseModel):
    start_date: date
    end_date: date
    daily_minutes: int = Field(default=120, ge=30, le=480)

    @model_validator(mode="after")
    def date_order(self):
        if self.start_date >= self.end_date:
            raise ValueError("开始日期必须在结束日期之前")
        return self


class TaskPatch(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(completed|postponed|skipped)$")
    scheduled_date: date | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)

    @model_validator(mode="after")
    def require_change(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("at least one field is required")
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    competency_name: str | None = None
    title: str
    description: str
    scheduled_date: date
    duration_minutes: int
    priority: int
    status: str
    created_at: datetime


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    goal: str
    start_date: date
    end_date: date
    version: int
    status: str
    created_at: datetime
    tasks: list[TaskOut] = Field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    coverage: float = 0.0
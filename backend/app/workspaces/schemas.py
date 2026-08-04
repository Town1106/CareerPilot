import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_role: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not (value := value.strip()):
            raise ValueError("name cannot be blank")
        return value


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    target_role: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is not None and not (value := value.strip()):
            raise ValueError("name cannot be blank")
        return value


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    target_role: str | None
    created_at: datetime
    updated_at: datetime

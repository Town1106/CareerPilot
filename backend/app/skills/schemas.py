import uuid
from datetime import datetime

from pydantic import BaseModel


class SkillOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str
    manifest_path: str
    risk_level: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillDetailOut(SkillOut):
    triggers: list[str]
    required_inputs: list[str]
    allowed_tools: list[str]


class SkillListOut(BaseModel):
    skills: list[SkillOut]
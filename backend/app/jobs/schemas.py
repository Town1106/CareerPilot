import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    raw_text: str = Field(min_length=50, max_length=30000)

    @field_validator("company", "title", "raw_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    company: str
    title: str
    raw_text: str
    status: str
    coverage_score: float | None
    analysis_error: str | None
    analyzed_at: datetime | None
    created_at: datetime


class ExtractedRequirement(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: Literal["technical", "experience", "responsibility", "soft_skill"]
    requirement_type: Literal["must", "preferred", "responsibility"]
    raw_evidence: str = Field(min_length=1, max_length=1000)


class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement] = Field(min_length=1, max_length=30)


class EvidenceJudgment(BaseModel):
    requirement_index: int = Field(ge=0)
    coverage: Literal["covered", "partial", "uncovered", "conflict"]
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=1000)
    evidence_labels: list[str] = Field(default_factory=list, max_length=5)


class JudgmentResult(BaseModel):
    judgments: list[EvidenceJudgment]


class EvidenceOut(BaseModel):
    chunk_id: uuid.UUID | None
    document_id: uuid.UUID | None
    original_name: str | None
    page_number: int | None
    content: str | None
    score: float
    support_level: str
    explanation: str


class RequirementOut(BaseModel):
    id: uuid.UUID
    competency: str
    category: str
    requirement_type: str
    importance: int
    raw_evidence: str
    coverage: str
    confidence: float
    explanation: str
    priority: float
    evidence: list[EvidenceOut]


class AnalysisOut(BaseModel):
    job: JobOut
    requirements: list[RequirementOut]


class CompareRequest(BaseModel):
    job_ids: list[uuid.UUID] = Field(min_length=2, max_length=10)


class CompetencyComparison(BaseModel):
    competency: str
    jobs: dict[str, str]


class CompareOut(BaseModel):
    jobs: list[JobOut]
    common: list[CompetencyComparison]
    differences: list[CompetencyComparison]


class GapOut(BaseModel):
    competency: str
    category: str
    worst_coverage: str
    max_importance: int
    priority: float
    job_count: int

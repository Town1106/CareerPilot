import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

InterviewType = Literal["technical", "project", "system_design", "behavioral", "mixed"]
QuestionSourceMode = Literal["all_real", "mixed", "no_search"]


class InterviewCreate(BaseModel):
    job_description_id: uuid.UUID
    interview_type: InterviewType = "mixed"
    question_limit: int = Field(default=10, ge=3, le=15)
    question_source_mode: QuestionSourceMode = "no_search"


class QuestionResult(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


class AnswerCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)

    @field_validator("answer", mode="before")
    @classmethod
    def strip_answer(cls, value):
        return value.strip() if isinstance(value, str) else value


class AnswerAssessment(BaseModel):
    quality: int = Field(ge=0, le=100)
    should_follow_up: bool
    observation: str = Field(min_length=1, max_length=1000)
    follow_up_question: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_follow_up_question(self):
        if self.should_follow_up and not self.follow_up_question:
            raise ValueError("follow_up_question is required")
        return self


class CompetencyScoreResult(BaseModel):
    competency: str = Field(min_length=1, max_length=120)
    score: int = Field(ge=0, le=100)
    rubric: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(min_length=1, max_length=5)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    issues: list[str] = Field(default_factory=list, max_length=5)
    suggestion: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence", "strengths", "issues", mode="before")
    @classmethod
    def accept_single_item(cls, value):
        return [value] if isinstance(value, str) else value


class InterviewReportResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=2000)
    strengths: list[str] = Field(default_factory=list, max_length=10)
    issues: list[str] = Field(default_factory=list, max_length=10)
    competency_scores: list[CompetencyScoreResult] = Field(min_length=1, max_length=20)

    @field_validator("strengths", "issues", mode="before")
    @classmethod
    def accept_single_item(cls, value):
        return [value] if isinstance(value, str) else value


class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    competency_name: str
    research_question_id: uuid.UUID | None
    source_type: str
    source_url: str | None
    sequence: int
    question: str
    answer: str | None
    is_follow_up: bool
    answered_at: datetime | None
    created_at: datetime


class ScoreOut(BaseModel):
    id: uuid.UUID
    competency_name: str
    score: int
    rubric: str
    evidence: list[str]
    strengths: list[str]
    issues: list[str]
    suggestion: str


class InterviewOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    job_description_id: uuid.UUID | None
    job_name: str | None
    interview_type: str
    question_limit: int
    question_source_mode: QuestionSourceMode
    status: str
    overall_score: float | None
    report_summary: str | None
    report_strengths: list[str]
    report_issues: list[str]
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    turns: list[TurnOut] = Field(default_factory=list)
    scores: list[ScoreOut] = Field(default_factory=list)


class MemoryPatch(BaseModel):
    mastery_score: float | None = Field(default=None, ge=0, le=100)
    evidence_summary: str | None = Field(default=None, min_length=1, max_length=2000)
    confirmed: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("at least one field is required")
        return self


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    source_session_id: uuid.UUID | None
    competency_name: str
    mastery_score: float
    confidence: float
    evidence_summary: str
    error_count: int
    confirmed: bool
    updated_at: datetime
    created_at: datetime

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utc_now


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))
    raw_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    analysis_raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Competency(Base):
    __tablename__ = "competencies"
    __table_args__ = (UniqueConstraint("workspace_id", "canonical_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    canonical_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_description_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )
    competency_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competencies.id", ondelete="CASCADE"), index=True
    )
    requirement_type: Mapped[str] = mapped_column(String(30))
    importance: Mapped[int] = mapped_column(Integer)
    raw_evidence: Mapped[str] = mapped_column(Text)
    coverage: Mapped[str] = mapped_column(String(20), default="uncovered")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="")


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requirements.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    score: Mapped[float] = mapped_column(Float)
    support_level: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)


class InterviewResearch(Base):
    __tablename__ = "interview_research"
    __table_args__ = (UniqueConstraint("job_description_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Kept nullable so existing installations can migrate without rebuilding this table.
    job_description_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(120))
    job_title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchQuestion(Base):
    __tablename__ = "research_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interview_research.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    competency: Mapped[str] = mapped_column(String(120))
    interview_stage: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String(500))
    excerpt: Mapped[str] = mapped_column(Text)
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

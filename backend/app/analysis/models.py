import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utc_now


class ProjectFact(Base):
    __tablename__ = "project_facts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    repo_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    extracted_tech_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extracted_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    extracted_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConsistencyReport(Base):
    __tablename__ = "consistency_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    repo_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    matched_items: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    missing_in_resume: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    conflicts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
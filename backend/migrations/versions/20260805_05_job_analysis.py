"""add job descriptions, competencies, requirements, and evidence"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_05"
down_revision = "20260805_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=True),
        sa.Column("analysis_error", sa.String(length=500), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_descriptions_workspace_id", "job_descriptions", ["workspace_id"])
    op.create_table(
        "competencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "canonical_name"),
    )
    op.create_index("ix_competencies_workspace_id", "competencies", ["workspace_id"])
    op.create_table(
        "job_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_description_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_type", sa.String(length=30), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("raw_evidence", sa.Text(), nullable=False),
        sa.Column("coverage", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_description_id"], ["job_descriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_requirements_competency_id", "job_requirements", ["competency_id"])
    op.create_index(
        "ix_job_requirements_job_description_id", "job_requirements", ["job_description_id"]
    )
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("support_level", sa.String(length=20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requirement_id"], ["job_requirements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_links_chunk_id", "evidence_links", ["chunk_id"])
    op.create_index("ix_evidence_links_requirement_id", "evidence_links", ["requirement_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_links_requirement_id", table_name="evidence_links")
    op.drop_index("ix_evidence_links_chunk_id", table_name="evidence_links")
    op.drop_table("evidence_links")
    op.drop_index("ix_job_requirements_job_description_id", table_name="job_requirements")
    op.drop_index("ix_job_requirements_competency_id", table_name="job_requirements")
    op.drop_table("job_requirements")
    op.drop_index("ix_competencies_workspace_id", table_name="competencies")
    op.drop_table("competencies")
    op.drop_index("ix_job_descriptions_workspace_id", table_name="job_descriptions")
    op.drop_table("job_descriptions")

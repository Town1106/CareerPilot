"""add interviews, reports, and competency memories"""

import sqlalchemy as sa
from alembic import op

revision = "20260805_06"
down_revision = "20260805_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("job_description_id", sa.Uuid(), nullable=True),
        sa.Column("interview_type", sa.String(30), nullable=False),
        sa.Column("question_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("report_summary", sa.Text(), nullable=True),
        sa.Column("report_strengths", sa.Text(), nullable=True),
        sa.Column("report_issues", sa.Text(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_description_id"], ["job_descriptions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sessions_workspace_id", "interview_sessions", ["workspace_id"])
    op.create_index(
        "ix_interview_sessions_job_description_id", "interview_sessions", ["job_description_id"]
    )
    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("competency_name", sa.String(120), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("is_follow_up", sa.Boolean(), nullable=False),
        sa.Column("private_observation", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_index("ix_interview_turns_session_id", "interview_turns", ["session_id"])
    op.create_index("ix_interview_turns_competency_id", "interview_turns", ["competency_id"])
    op.create_table(
        "interview_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("competency_name", sa.String(120), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("rubric", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("issues", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "competency_name"),
    )
    op.create_index("ix_interview_scores_session_id", "interview_scores", ["session_id"])
    op.create_table(
        "competency_memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("source_session_id", sa.Uuid(), nullable=True),
        sa.Column("competency_name", sa.String(120), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competency_id"], ["competencies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_session_id"], ["interview_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "competency_name"),
    )
    op.create_index("ix_competency_memories_workspace_id", "competency_memories", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_competency_memories_workspace_id", table_name="competency_memories")
    op.drop_table("competency_memories")
    op.drop_index("ix_interview_scores_session_id", table_name="interview_scores")
    op.drop_table("interview_scores")
    op.drop_index("ix_interview_turns_competency_id", table_name="interview_turns")
    op.drop_index("ix_interview_turns_session_id", table_name="interview_turns")
    op.drop_table("interview_turns")
    op.drop_index("ix_interview_sessions_job_description_id", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_workspace_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")

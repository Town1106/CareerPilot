"""add web interview research and question sources"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_07"
down_revision = "20260805_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_research",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_description_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_description_id"], ["job_descriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_description_id"),
    )
    op.create_index(
        "ix_interview_research_job_description_id", "interview_research", ["job_description_id"]
    )
    op.create_table(
        "research_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("research_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("competency", sa.String(120), nullable=False),
        sa.Column("interview_stage", sa.String(30), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["research_id"], ["interview_research.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_questions_research_id", "research_questions", ["research_id"])
    op.add_column(
        "interview_sessions",
        sa.Column("use_web_research", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    with op.batch_alter_table("interview_turns") as batch_op:
        batch_op.add_column(sa.Column("research_question_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("source_type", sa.String(30), server_default="job_gap", nullable=False)
        )
        batch_op.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_interview_turns_research_question_id",
            "research_questions",
            ["research_question_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_interview_turns_research_question_id",
        "interview_turns",
        ["research_question_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_turns_research_question_id", table_name="interview_turns")
    with op.batch_alter_table("interview_turns") as batch_op:
        batch_op.drop_constraint("fk_interview_turns_research_question_id", type_="foreignkey")
        batch_op.drop_column("source_url")
        batch_op.drop_column("source_type")
        batch_op.drop_column("research_question_id")
    op.drop_column("interview_sessions", "use_web_research")
    op.drop_index("ix_research_questions_research_id", table_name="research_questions")
    op.drop_table("research_questions")
    op.drop_index("ix_interview_research_job_description_id", table_name="interview_research")
    op.drop_table("interview_research")

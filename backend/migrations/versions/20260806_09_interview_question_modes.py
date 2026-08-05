"""move interview research to company-role pools"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_09"
down_revision = "20260806_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_research", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.add_column("interview_research", sa.Column("company", sa.String(120), nullable=True))
    op.add_column("interview_research", sa.Column("job_title", sa.String(120), nullable=True))
    op.execute(
        """
        UPDATE interview_research
        SET workspace_id = (
                SELECT workspace_id FROM job_descriptions
                WHERE job_descriptions.id = interview_research.job_description_id
            ),
            company = (
                SELECT company FROM job_descriptions
                WHERE job_descriptions.id = interview_research.job_description_id
            ),
            job_title = (
                SELECT title FROM job_descriptions
                WHERE job_descriptions.id = interview_research.job_description_id
            )
        """
    )
    with op.batch_alter_table("interview_research") as batch_op:
        batch_op.alter_column("job_description_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.alter_column("workspace_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column("company", existing_type=sa.String(120), nullable=False)
        batch_op.alter_column("job_title", existing_type=sa.String(120), nullable=False)
        batch_op.create_foreign_key(
            "fk_interview_research_workspace_id",
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.execute("UPDATE interview_research SET job_description_id = NULL")
    op.create_index("ix_interview_research_workspace_id", "interview_research", ["workspace_id"])

    op.add_column(
        "research_questions",
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "research_questions",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "interview_sessions",
        sa.Column(
            "question_source_mode",
            sa.String(20),
            server_default="no_search",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE interview_sessions
        SET question_source_mode = CASE
            WHEN use_web_research THEN 'mixed'
            ELSE 'no_search'
        END
        """
    )
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.drop_column("use_web_research")


def downgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("use_web_research", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.execute(
        "UPDATE interview_sessions SET use_web_research = "
        "CASE WHEN question_source_mode = 'no_search' THEN false ELSE true END"
    )
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.drop_column("question_source_mode")

    op.drop_column("research_questions", "last_used_at")
    op.drop_column("research_questions", "use_count")
    op.drop_index("ix_interview_research_workspace_id", table_name="interview_research")
    with op.batch_alter_table("interview_research") as batch_op:
        batch_op.drop_constraint("fk_interview_research_workspace_id", type_="foreignkey")
        batch_op.drop_column("job_title")
        batch_op.drop_column("company")
        batch_op.drop_column("workspace_id")

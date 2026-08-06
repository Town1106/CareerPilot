"""add project_facts and consistency_reports tables"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260806_14"
down_revision = "20260806_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("repo_full_name", sa.String(200), nullable=False),
        sa.Column("extracted_tech_stack", postgresql.JSON, nullable=True),
        sa.Column("extracted_summary", sa.String(2000), nullable=True),
        sa.Column("extracted_role", sa.String(200), nullable=True),
        sa.Column("commit_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "consistency_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("repo_full_name", sa.String(200), nullable=False),
        sa.Column("matched_items", postgresql.JSON, nullable=True),
        sa.Column("missing_in_resume", postgresql.JSON, nullable=True),
        sa.Column("conflicts", postgresql.JSON, nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("consistency_reports")
    op.drop_table("project_facts")
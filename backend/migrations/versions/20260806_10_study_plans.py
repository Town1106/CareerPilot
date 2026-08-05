"""add study_plans and study_tasks"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_10"
down_revision = "20260806_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_plans_workspace_id", "study_plans", ["workspace_id"])

    op.create_table(
        "study_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("competency_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("external_event_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["competency_id"], ["competencies.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["study_plans.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_tasks_plan_id", "study_tasks", ["plan_id"])


def downgrade() -> None:
    op.drop_table("study_tasks")
    op.drop_table("study_plans")
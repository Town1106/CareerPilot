"""add tool_definitions, tool_policies, tool_approvals tables"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_13"
down_revision = "20260806_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("manifest_path", sa.String(300), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="R0"),
        sa.Column("input_schema", sa.String(2000), nullable=True),
        sa.Column("output_schema", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "tool_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column("require_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_prompt", sa.String(500), nullable=True),
        sa.Column("max_per_session", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tool_name"], ["tool_definitions.name"], ondelete="CASCADE"),
    )

    op.create_table(
        "tool_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_skill", sa.String(80), nullable=True),
        sa.Column("payload_summary", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("tool_approvals")
    op.drop_table("tool_policies")
    op.drop_table("tool_definitions")
"""add skill_definitions table and skill fields to agent_runs"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_12"
down_revision = "20260806_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("manifest_path", sa.String(300), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="R0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column("agent_runs", sa.Column("skill_name", sa.String(80), nullable=True))
    op.add_column("agent_runs", sa.Column("skill_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "skill_version")
    op.drop_column("agent_runs", "skill_name")
    op.drop_table("skill_definitions")
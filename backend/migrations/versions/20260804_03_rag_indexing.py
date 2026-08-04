"""add document indexing status"""

import sqlalchemy as sa
from alembic import op

revision = "20260804_03"
down_revision = "20260804_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("index_error", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE documents SET status = 'parsed' WHERE status = 'ready'")


def downgrade() -> None:
    op.execute(
        "UPDATE documents SET status = 'ready' WHERE status IN ('parsed', 'indexed', 'failed')"
    )
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "index_error")

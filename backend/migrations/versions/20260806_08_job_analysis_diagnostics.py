"""store job analysis raw output"""

import sqlalchemy as sa
from alembic import op

revision = "20260806_08"
down_revision = "20260806_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_descriptions", sa.Column("analysis_raw_output", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_descriptions", "analysis_raw_output")

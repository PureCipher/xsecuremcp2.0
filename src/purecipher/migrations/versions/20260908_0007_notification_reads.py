"""Persist per-account notification read state."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0007"
down_revision = "20260908_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purecipher_notification_reads",
        sa.Column("username", sa.Text(), primary_key=True),
        sa.Column("notification_id", sa.BigInteger(), primary_key=True),
    )


def downgrade():
    op.drop_table("purecipher_notification_reads")

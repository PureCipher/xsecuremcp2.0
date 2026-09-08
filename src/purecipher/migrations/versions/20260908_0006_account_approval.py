"""Persist registration requests and administrator decisions."""

import sqlalchemy as sa
from alembic import op

revision = "20260908_0006"
down_revision = "20260906_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "purecipher_registry_accounts",
        sa.Column("registration", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade():
    op.drop_column("purecipher_registry_accounts", "registration")

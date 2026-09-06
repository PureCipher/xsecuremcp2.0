"""Persistent private profiles and immutable client ownership bindings."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0005"
down_revision = "20260428_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purecipher_workspace",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index("ix_workspace_owner", "purecipher_workspace", ["owner", "kind"])


def downgrade():
    op.drop_table("purecipher_workspace")

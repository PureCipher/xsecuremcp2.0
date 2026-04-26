"""Add MCP client identity + token tables (Iter 10).

Iteration 10 adds first-class MCP-client identities to the
registry. Two tables: ``purecipher_registry_clients`` for the
identity records, ``purecipher_registry_client_tokens`` for the
opaque API tokens issued to each client. The matching store is
``purecipher.clients.RegistryClientStore``.

Revision ID: 20260427_0003
Revises: 20260426_0002
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260427_0003"
down_revision: str | None = "20260426_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "purecipher_registry_clients" not in tables:
        op.create_table(
            "purecipher_registry_clients",
            sa.Column("client_id", sa.Text(), primary_key=True),
            sa.Column("slug", sa.Text(), nullable=False, unique=True),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("intended_use", sa.Text(), nullable=False),
            sa.Column(
                "kind", sa.Text(), nullable=False, server_default="agent"
            ),
            sa.Column("owner_publisher_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("suspended_reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("updated_at", sa.REAL(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=False),
        )

    if "purecipher_registry_client_tokens" not in tables:
        op.create_table(
            "purecipher_registry_client_tokens",
            sa.Column("token_id", sa.Text(), primary_key=True),
            sa.Column("client_id", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("secret_hash", sa.Text(), nullable=False, unique=True),
            sa.Column("secret_prefix", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=False),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("revoked_at", sa.REAL(), nullable=True),
            sa.Column("last_used_at", sa.REAL(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("purecipher_registry_client_tokens")
    op.drop_table("purecipher_registry_clients")

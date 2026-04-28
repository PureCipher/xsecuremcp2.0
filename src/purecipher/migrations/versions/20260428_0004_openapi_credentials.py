"""Add encrypted OpenAPI credentials table (Iter 13.2).

Iteration 13.2 introduces per-publisher / per-source / per-scheme
credential storage for the OpenAPI helper. Secrets are encrypted at
rest with Fernet keyed off the registry signing secret. The schema
intentionally separates the searchable hint (last-4 / masked username)
from the ciphertext so the listing endpoint can return the hint
without ever decrypting.

Revision ID: 20260428_0004
Revises: 20260427_0003
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0004"
down_revision: str | None = "20260427_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "purecipher_openapi_credentials" not in tables:
        op.create_table(
            "purecipher_openapi_credentials",
            sa.Column("credential_id", sa.Text(), primary_key=True),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("updated_at", sa.REAL(), nullable=False),
            sa.Column("publisher_id", sa.Text(), nullable=False),
            sa.Column("source_id", sa.Text(), nullable=False),
            sa.Column("scheme_name", sa.Text(), nullable=False),
            sa.Column("scheme_kind", sa.Text(), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("secret_hint", sa.Text(), nullable=False),
            sa.Column("secret_ciphertext", sa.Text(), nullable=False),
            sa.UniqueConstraint(
                "publisher_id",
                "source_id",
                "scheme_name",
                name="uq_purecipher_openapi_credentials_triple",
            ),
        )


def downgrade() -> None:
    op.drop_table("purecipher_openapi_credentials")

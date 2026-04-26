"""Add the control-plane toggle table (Iter 9).

Persists operator toggles for the four opt-in SecureMCP control
planes (contracts / consent / provenance / reflexive). The table
shape is intentionally tiny: one row per plane, last actor +
timestamp preserved for audit. The matching store is
``purecipher.control_plane_settings.RegistryControlPlaneStore``.

Revision ID: 20260426_0002
Revises: 20260425_0001
Create Date: 2026-04-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_0002"
down_revision: str | None = "20260425_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "purecipher_registry_control_planes" not in tables:
        op.create_table(
            "purecipher_registry_control_planes",
            sa.Column("plane", sa.Text(), primary_key=True),
            sa.Column("enabled", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.REAL(), nullable=False),
            sa.Column("updated_by", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("purecipher_registry_control_planes")

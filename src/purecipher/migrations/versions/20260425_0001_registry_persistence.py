"""Create PureCipher registry persistence tables.

Revision ID: 20260425_0001
Revises:
Create Date: 2026-04-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260425_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "purecipher_registry_notifications" not in tables:
        op.create_table(
            "purecipher_registry_notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("event_kind", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("link_path", sa.Text(), nullable=True),
            sa.Column("audiences_json", sa.Text(), nullable=False),
        )

    if "purecipher_openapi_sources" not in tables:
        op.create_table(
            "purecipher_openapi_sources",
            sa.Column("source_id", sa.Text(), primary_key=True),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("publisher_id", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("spec_json", sa.Text(), nullable=False),
            sa.Column("spec_sha256", sa.Text(), nullable=False),
            sa.Column("operation_count", sa.Integer(), nullable=False),
        )

    if "purecipher_openapi_toolsets" not in tables:
        op.create_table(
            "purecipher_openapi_toolsets",
            sa.Column("toolset_id", sa.Text(), primary_key=True),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("publisher_id", sa.Text(), nullable=False),
            sa.Column("source_id", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("selected_operations_json", sa.Text(), nullable=False),
            sa.Column("tool_name_prefix", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=False),
        )

    if "purecipher_registry_user_preferences" not in tables:
        op.create_table(
            "purecipher_registry_user_preferences",
            sa.Column("username", sa.Text(), primary_key=True),
            sa.Column("preferences_json", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.REAL(), nullable=False),
        )

    if "purecipher_registry_account_activity" not in tables:
        op.create_table(
            "purecipher_registry_account_activity",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("username", sa.Text(), nullable=False),
            sa.Column("event_kind", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=False),
        )

    if "purecipher_registry_accounts" not in tables:
        op.create_table(
            "purecipher_registry_accounts",
            sa.Column("username", sa.Text(), primary_key=True),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.REAL(), nullable=False),
            sa.Column("created_at", sa.REAL(), nullable=True),
            sa.Column("disabled_at", sa.REAL(), nullable=True),
        )
    else:
        _add_missing_account_columns()

    if "purecipher_registry_sessions" not in tables:
        op.create_table(
            "purecipher_registry_sessions",
            sa.Column("session_id", sa.Text(), primary_key=True),
            sa.Column("username", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("expires_at", sa.REAL(), nullable=False),
            sa.Column("revoked_at", sa.REAL(), nullable=True),
        )

    if "purecipher_registry_api_tokens" not in tables:
        op.create_table(
            "purecipher_registry_api_tokens",
            sa.Column("token_id", sa.Text(), primary_key=True),
            sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
            sa.Column("username", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.REAL(), nullable=False),
            sa.Column("last_used_at", sa.REAL(), nullable=True),
            sa.Column("revoked_at", sa.REAL(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("purecipher_registry_api_tokens")
    op.drop_table("purecipher_registry_sessions")
    op.drop_table("purecipher_registry_accounts")
    op.drop_table("purecipher_registry_account_activity")
    op.drop_table("purecipher_registry_user_preferences")
    op.drop_table("purecipher_openapi_toolsets")
    op.drop_table("purecipher_openapi_sources")
    op.drop_table("purecipher_registry_notifications")


def _add_missing_account_columns() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("purecipher_registry_accounts")
    }
    if "created_at" not in columns:
        op.add_column(
            "purecipher_registry_accounts",
            sa.Column("created_at", sa.REAL(), nullable=True),
        )
    if "disabled_at" not in columns:
        op.add_column(
            "purecipher_registry_accounts",
            sa.Column("disabled_at", sa.REAL(), nullable=True),
        )
    bind.execute(
        sa.text(
            "UPDATE purecipher_registry_accounts "
            "SET created_at = updated_at "
            "WHERE created_at IS NULL"
        )
    )

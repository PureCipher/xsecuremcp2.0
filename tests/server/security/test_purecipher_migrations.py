from __future__ import annotations

import psycopg

from purecipher.db_migrations import migrate_registry_database


def test_alembic_migration_creates_registry_tables(registry_dsn):
    # The registry_dsn fixture already migrates to head; re-running is
    # idempotent and mirrors how the CLI/registry invoke the migration.
    migrate_registry_database(registry_dsn)

    with psycopg.connect(registry_dsn) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ).fetchall()
        }
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()

    assert version == ("20260428_0004",)
    assert "purecipher_registry_accounts" in tables
    assert "purecipher_registry_sessions" in tables
    assert "purecipher_registry_api_tokens" in tables
    assert "purecipher_registry_user_preferences" in tables
    assert "purecipher_registry_account_activity" in tables
    assert "purecipher_registry_notifications" in tables
    assert "purecipher_openapi_sources" in tables
    assert "purecipher_openapi_toolsets" in tables
    # Iter 9: control-plane toggles persistent store.
    assert "purecipher_registry_control_planes" in tables
    # Iter 10: MCP-client identity + token tables.
    assert "purecipher_registry_clients" in tables
    assert "purecipher_registry_client_tokens" in tables
    # Iter 13.2: encrypted OpenAPI credentials.
    assert "purecipher_openapi_credentials" in tables


def test_alembic_migration_creates_account_activity_columns(registry_dsn):
    migrate_registry_database(registry_dsn)

    with psycopg.connect(registry_dsn) as conn:
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = 'purecipher_registry_accounts'"
            ).fetchall()
        }

    assert "created_at" in columns
    assert "disabled_at" in columns

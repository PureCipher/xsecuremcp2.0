from __future__ import annotations

import sqlite3

from purecipher.db_migrations import migrate_registry_database


def test_alembic_migration_creates_registry_tables(tmp_path):
    db_path = tmp_path / "registry.sqlite"

    migrate_registry_database(str(db_path))

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    conn.close()

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


def test_alembic_migration_upgrades_legacy_account_table(tmp_path):
    db_path = tmp_path / "registry.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE purecipher_registry_accounts (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO purecipher_registry_accounts
            (username, password_hash, role, display_name, source, updated_at)
        VALUES ('admin', 'hash', 'admin', 'Registry Admin', 'seed', 42.0)
        """
    )
    conn.commit()
    conn.close()

    migrate_registry_database(str(db_path))

    conn = sqlite3.connect(db_path)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(purecipher_registry_accounts)")
    }
    created_at = conn.execute(
        "SELECT created_at FROM purecipher_registry_accounts WHERE username = 'admin'"
    ).fetchone()
    conn.close()

    assert "created_at" in columns
    assert "disabled_at" in columns
    assert created_at == (42.0,)

"""User preference persistence for the PureCipher registry UI."""

from __future__ import annotations

import json
import time
from typing import Any

from purecipher.pgdb import connection, is_postgres_dsn

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "notifications": {
        "publishUpdates": True,
        "reviewQueue": True,
        "policyChanges": True,
        "securityAlerts": True,
    },
    "workspace": {
        "defaultLandingPage": "/registry/app",
        "density": "comfortable",
    },
    "publisher": {
        "defaultCertification": "basic",
        "openMineFirst": True,
    },
    "reviewer": {
        "defaultLane": "pending",
        "highRiskFirst": True,
    },
    "admin": {
        "defaultAdminView": "health",
        "requireConfirmations": True,
    },
}


def _deep_merge_defaults(value: dict[str, Any] | None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    merged: dict[str, Any] = {}
    for section, defaults in DEFAULT_USER_PREFERENCES.items():
        section_value = source.get(section)
        if isinstance(defaults, dict):
            merged[section] = {
                **defaults,
                **(section_value if isinstance(section_value, dict) else {}),
            }
        else:
            merged[section] = section_value if section in source else defaults
    return merged


class RegistryUserPreferenceStore:
    """Store registry UI preferences per username.

    Uses the registry PostgreSQL database when available and falls back to
    in-memory storage for test/dev registries without persistence.
    """

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        self._db_path = db_path
        self._memory: dict[str, dict[str, Any]] = {}
        if is_postgres_dsn(self._db_path) and ensure_schema:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        assert self._db_path is not None
        with connection(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purecipher_registry_user_preferences (
                    username TEXT PRIMARY KEY,
                    preferences_json TEXT NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                );
                """
            )

    def get(self, username: str) -> dict[str, Any]:
        key = username.strip()
        if not key:
            return _deep_merge_defaults(None)

        if not is_postgres_dsn(self._db_path):
            return _deep_merge_defaults(self._memory.get(key))

        with connection(self._db_path) as conn:
            cur = conn.execute(
                "SELECT preferences_json FROM purecipher_registry_user_preferences WHERE username = %s",
                (key,),
            )
            row = cur.fetchone()
        if row is None:
            return _deep_merge_defaults(None)
        try:
            parsed = json.loads(str(row[0]))
        except json.JSONDecodeError:
            parsed = None
        return _deep_merge_defaults(parsed if isinstance(parsed, dict) else None)

    def set(self, username: str, preferences: dict[str, Any]) -> dict[str, Any]:
        key = username.strip()
        if not key:
            raise ValueError("username is required")
        merged = _deep_merge_defaults(preferences)

        if not is_postgres_dsn(self._db_path):
            self._memory[key] = merged
            return merged

        with connection(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO purecipher_registry_user_preferences
                    (username, preferences_json, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    preferences_json = EXCLUDED.preferences_json,
                    updated_at = EXCLUDED.updated_at
                """,
                (key, json.dumps(merged, sort_keys=True), time.time()),
            )
        return merged

    def reset(self, username: str) -> dict[str, Any]:
        key = username.strip()
        if not key:
            raise ValueError("username is required")

        if not is_postgres_dsn(self._db_path):
            self._memory.pop(key, None)
            return _deep_merge_defaults(None)

        with connection(self._db_path) as conn:
            conn.execute(
                "DELETE FROM purecipher_registry_user_preferences WHERE username = %s",
                (key,),
            )
        return _deep_merge_defaults(None)


__all__ = [
    "DEFAULT_USER_PREFERENCES",
    "RegistryUserPreferenceStore",
]

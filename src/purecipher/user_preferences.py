"""User preference persistence for the PureCipher registry UI."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

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

    Uses the registry SQLite file when available and falls back to in-memory
    storage for test/dev registries without persistence.
    """

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        self._db_path = db_path
        self._memory: dict[str, dict[str, Any]] = {}
        if self._db_path and ensure_schema:
            self._ensure_sqlite()

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_user_preferences (
                username TEXT PRIMARY KEY,
                preferences_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def get(self, username: str) -> dict[str, Any]:
        key = username.strip()
        if not key:
            return _deep_merge_defaults(None)

        if not self._db_path:
            return _deep_merge_defaults(self._memory.get(key))

        conn = sqlite3.connect(self._db_path)
        cur = conn.execute(
            "SELECT preferences_json FROM purecipher_registry_user_preferences WHERE username = ?",
            (key,),
        )
        row = cur.fetchone()
        conn.close()
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

        if not self._db_path:
            self._memory[key] = merged
            return merged

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            INSERT INTO purecipher_registry_user_preferences
                (username, preferences_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                preferences_json = excluded.preferences_json,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(merged, sort_keys=True), time.time()),
        )
        conn.commit()
        conn.close()
        return merged

    def reset(self, username: str) -> dict[str, Any]:
        key = username.strip()
        if not key:
            raise ValueError("username is required")

        if not self._db_path:
            self._memory.pop(key, None)
            return _deep_merge_defaults(None)

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "DELETE FROM purecipher_registry_user_preferences WHERE username = ?",
            (key,),
        )
        conn.commit()
        conn.close()
        return _deep_merge_defaults(None)


__all__ = [
    "DEFAULT_USER_PREFERENCES",
    "RegistryUserPreferenceStore",
]

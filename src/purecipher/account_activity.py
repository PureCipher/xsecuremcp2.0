"""Account security activity persistence for the PureCipher registry UI."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

_MAX_ITEMS = 200


class RegistryAccountActivityStore:
    """Store recent account activity in SQLite or memory."""

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        # ``:memory:`` is treated as in-memory (deque) rather than as
        # a literal SQLite path. ``sqlite3.connect(":memory:")`` opens
        # a fresh isolated database on every call, so the schema
        # created in ``_ensure_sqlite`` would vanish by the time
        # ``append`` reopened the connection. The other registry
        # stores (clients, control planes) use the same convention.
        if db_path == ":memory:":
            db_path = None
        self._db_path = db_path
        self._memory: deque[dict[str, Any]] = deque(maxlen=_MAX_ITEMS)
        self._mem_seq = 0
        if self._db_path and ensure_schema:
            self._ensure_sqlite()

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_account_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                username TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def append(
        self,
        *,
        username: str,
        event_kind: str,
        title: str,
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        username_value = username.strip() or "unknown"
        metadata_json = json.dumps(dict(metadata or {}), sort_keys=True)
        now = time.time()
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO purecipher_registry_account_activity "
                "(created_at, username, event_kind, title, detail, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, username_value, event_kind, title, detail, metadata_json),
            )
            conn.commit()
            conn.close()
            return

        self._mem_seq += 1
        self._memory.appendleft(
            {
                "id": self._mem_seq,
                "created_at": now,
                "username": username_value,
                "event_kind": event_kind,
                "title": title,
                "detail": detail,
                "metadata_json": metadata_json,
            }
        )

    def list_recent(self, *, username: str, limit: int = 20) -> list[dict[str, Any]]:
        username_value = username.strip()
        if not username_value:
            return []
        cap = min(max(limit, 1), _MAX_ITEMS)

        rows: list[tuple[Any, ...]]
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT id, created_at, username, event_kind, title, detail, metadata_json "
                "FROM purecipher_registry_account_activity "
                "WHERE username = ? "
                "ORDER BY id DESC LIMIT ?",
                (username_value, cap),
            )
            rows = cur.fetchall()
            conn.close()
        else:
            rows = [
                (
                    row["id"],
                    row["created_at"],
                    row["username"],
                    row["event_kind"],
                    row["title"],
                    row["detail"],
                    row["metadata_json"],
                )
                for row in list(self._memory)
                if row["username"] == username_value
            ][:cap]

        out: list[dict[str, Any]] = []
        for row in rows:
            id_, created_at, row_username, event_kind, title, detail, metadata_json = row
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
            out.append(
                {
                    "id": id_,
                    "created_at": datetime.fromtimestamp(
                        float(created_at),
                        tz=timezone.utc,
                    ).isoformat(),
                    "username": row_username,
                    "event_kind": event_kind,
                    "title": title,
                    "detail": detail,
                    "metadata": metadata if isinstance(metadata, dict) else {},
                }
            )
        return out


__all__ = ["RegistryAccountActivityStore"]

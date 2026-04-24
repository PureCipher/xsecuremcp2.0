"""Durable in-app notification feed for the PureCipher registry UI."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

_MAX_ITEMS = 200
_FETCH_MULTIPLIER = 4


def _visible_to_session(
    audiences: tuple[str, ...],
    *,
    auth_enabled: bool,
    role: str | None,
) -> bool:
    if not auth_enabled:
        return True
    if not audiences:
        return True
    effective = role if role in {"viewer", "publisher", "reviewer", "admin"} else "viewer"
    return effective in audiences


class RegistryNotificationFeed:
    """Append-only feed stored in the registry SQLite file or in memory."""

    def __init__(self, db_path: str | None) -> None:
        self._db_path = db_path
        self._memory: deque[dict[str, Any]] = deque(maxlen=_MAX_ITEMS)
        self._mem_seq = 0
        if self._db_path:
            self._ensure_sqlite()

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                event_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                link_path TEXT,
                audiences_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def append(
        self,
        *,
        event_kind: str,
        title: str,
        body: str,
        link_path: str | None = None,
        audiences: tuple[str, ...] | None = None,
    ) -> None:
        audiences_json = json.dumps(list(audiences) if audiences else [])
        now = time.time()
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO purecipher_registry_notifications "
                "(created_at, event_kind, title, body, link_path, audiences_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now, event_kind, title, body, link_path, audiences_json),
            )
            conn.commit()
            conn.close()
        else:
            self._mem_seq += 1
            self._memory.appendleft(
                {
                    "id": self._mem_seq,
                    "created_at": now,
                    "event_kind": event_kind,
                    "title": title,
                    "body": body,
                    "link_path": link_path,
                    "audiences_json": audiences_json,
                }
            )

    def list_recent(
        self,
        *,
        auth_enabled: bool,
        role: str | None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        cap = min(limit * _FETCH_MULTIPLIER, _MAX_ITEMS * _FETCH_MULTIPLIER)
        rows: list[tuple[Any, ...]]
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT id, created_at, event_kind, title, body, link_path, audiences_json "
                "FROM purecipher_registry_notifications "
                "ORDER BY id DESC LIMIT ?",
                (cap,),
            )
            rows = cur.fetchall()
            conn.close()
        else:
            rows = []
            for row in list(self._memory)[:cap]:
                rows.append(
                    (
                        row["id"],
                        row["created_at"],
                        row["event_kind"],
                        row["title"],
                        row["body"],
                        row["link_path"],
                        row["audiences_json"],
                    )
                )

        out: list[dict[str, Any]] = []
        for tup in rows:
            id_, created_at, event_kind, title, body, link_path, audiences_json = tup
            try:
                aud_list = json.loads(audiences_json)
                audiences_t = (
                    tuple(str(x) for x in aud_list) if isinstance(aud_list, list) else ()
                )
            except json.JSONDecodeError:
                audiences_t = ()
            if not _visible_to_session(
                audiences_t, auth_enabled=auth_enabled, role=role
            ):
                continue
            ts = datetime.fromtimestamp(float(created_at), tz=timezone.utc).isoformat()
            out.append(
                {
                    "id": id_,
                    "created_at": ts,
                    "event_kind": event_kind,
                    "title": title,
                    "body": body,
                    "link_path": link_path,
                }
            )
            if len(out) >= limit:
                break
        return out

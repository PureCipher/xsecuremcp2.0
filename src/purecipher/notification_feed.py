"""Durable in-app notification feed for the PureCipher registry UI."""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from purecipher.pgdb import connection, is_postgres_dsn

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
    effective = (
        role if role in {"viewer", "publisher", "reviewer", "admin"} else "viewer"
    )
    return effective in audiences


class RegistryNotificationFeed:
    """Append-only feed stored in the registry PostgreSQL database or in memory."""

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        self._db_path = db_path
        self._memory: deque[dict[str, Any]] = deque(maxlen=_MAX_ITEMS)
        self._mem_seq = 0
        if is_postgres_dsn(self._db_path) and ensure_schema:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        assert self._db_path is not None
        with connection(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purecipher_registry_notifications (
                    id BIGSERIAL PRIMARY KEY,
                    created_at DOUBLE PRECISION NOT NULL,
                    event_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    link_path TEXT,
                    audiences_json TEXT NOT NULL
                );
                """
            )

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
        if is_postgres_dsn(self._db_path):
            with connection(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO purecipher_registry_notifications "
                    "(created_at, event_kind, title, body, link_path, audiences_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (now, event_kind, title, body, link_path, audiences_json),
                )
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
        if is_postgres_dsn(self._db_path):
            with connection(self._db_path) as conn:
                cur = conn.execute(
                    "SELECT id, created_at, event_kind, title, body, link_path, audiences_json "
                    "FROM purecipher_registry_notifications "
                    "ORDER BY id DESC LIMIT %s",
                    (cap,),
                )
                rows = cur.fetchall()
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
                    tuple(str(x) for x in aud_list)
                    if isinstance(aud_list, list)
                    else ()
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

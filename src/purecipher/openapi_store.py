"""OpenAPI ingestion and toolset storage for the PureCipher registry.

This is intentionally a small MVP:
- Accept JSON OpenAPI payloads (3.0/3.1)
- Extract operations (method+path+operationId/summary/description)
- Persist to the registry SQLite file when available

Tool schema generation and gateway execution are layered on top of this store.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

HttpMethod = Literal["get", "post", "put", "patch", "delete", "head", "options"]


class OpenAPIOperation(TypedDict, total=False):
    operation_key: str
    method: HttpMethod
    path: str
    operation_id: str
    summary: str
    description: str
    tags: list[str]


class OpenAPISourceRecord(TypedDict, total=False):
    source_id: str
    created_at: float
    publisher_id: str
    title: str
    source_url: str
    spec_json: dict[str, Any]
    spec_sha256: str
    operation_count: int


class OpenAPIToolsetRecord(TypedDict, total=False):
    toolset_id: str
    created_at: float
    publisher_id: str
    source_id: str
    title: str
    selected_operations: list[str]
    tool_name_prefix: str
    metadata: dict[str, Any]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> float:
    return float(time.time())


def _coerce_openapi_json(raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAPI document is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must decode to a JSON object.")
    return payload


def extract_openapi_operations(spec: dict[str, Any]) -> list[OpenAPIOperation]:
    """Extract operation inventory from an OpenAPI document.

    MVP: does not resolve $refs or deeply inspect schemas.
    """

    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return []

    out: list[OpenAPIOperation] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            m = str(method).lower()
            if m not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(op, dict):
                continue

            operation_id = str(op.get("operationId") or "").strip()
            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            tags = op.get("tags")
            tags_list = [str(t) for t in tags] if isinstance(tags, list) else []

            operation_key = operation_id or f"{m.upper()} {path}"
            out.append(
                {
                    "operation_key": operation_key,
                    "method": m,  # type: ignore[typeddict-item]
                    "path": str(path),
                    "operation_id": operation_id,
                    "summary": summary,
                    "description": description,
                    "tags": tags_list,
                }
            )

    # Stable ordering for UI and tests
    out.sort(key=lambda item: (item.get("path", ""), item.get("method", ""), item.get("operation_key", "")))
    return out


@dataclass
class OpenAPIStore:
    """Persists OpenAPI sources + toolset selections."""

    db_path: str | None = None
    ensure_schema: bool = True

    def __post_init__(self) -> None:
        self._memory_sources: dict[str, OpenAPISourceRecord] = {}
        self._memory_toolsets: dict[str, OpenAPIToolsetRecord] = {}
        self._shared_conn: sqlite3.Connection | None = None
        if self.db_path:
            if self.db_path == ":memory:":
                # Keep a single connection so tables persist.
                self._shared_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            if self.ensure_schema:
                self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path:
            raise RuntimeError("OpenAPIStore is not configured with a sqlite path.")
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self.db_path)

    def _ensure_tables(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_openapi_sources (
              source_id TEXT PRIMARY KEY,
              created_at REAL NOT NULL,
              publisher_id TEXT NOT NULL,
              title TEXT NOT NULL,
              source_url TEXT NOT NULL,
              spec_json TEXT NOT NULL,
              spec_sha256 TEXT NOT NULL,
              operation_count INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_openapi_toolsets (
              toolset_id TEXT PRIMARY KEY,
              created_at REAL NOT NULL,
              publisher_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              title TEXT NOT NULL,
              selected_operations_json TEXT NOT NULL,
              tool_name_prefix TEXT NOT NULL,
              metadata_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()

    def ingest_source(
        self,
        *,
        publisher_id: str,
        title: str,
        source_url: str = "",
        raw_text: str,
    ) -> tuple[OpenAPISourceRecord, list[OpenAPIOperation]]:
        spec = _coerce_openapi_json(raw_text)
        ops = extract_openapi_operations(spec)
        spec_sha = _sha256_text(json.dumps(spec, sort_keys=True, separators=(",", ":")))
        source_id = f"oas_{spec_sha[:24]}"
        record: OpenAPISourceRecord = {
            "source_id": source_id,
            "created_at": _now(),
            "publisher_id": publisher_id,
            "title": title.strip() or "OpenAPI source",
            "source_url": source_url.strip(),
            "spec_json": spec,
            "spec_sha256": spec_sha,
            "operation_count": len(ops),
        }

        if not self.db_path:
            self._memory_sources[source_id] = record
            return record, ops

        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO purecipher_openapi_sources
              (source_id, created_at, publisher_id, title, source_url, spec_json, spec_sha256, operation_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                record["created_at"],
                record["publisher_id"],
                record["title"],
                record["source_url"],
                json.dumps(spec),
                record["spec_sha256"],
                record["operation_count"],
            ),
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return record, ops

    def create_toolset(
        self,
        *,
        publisher_id: str,
        source_id: str,
        title: str,
        selected_operations: list[str],
        tool_name_prefix: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OpenAPIToolsetRecord:
        toolset_id = f"toolset_{hashlib.sha256((publisher_id + ':' + source_id + ':' + title).encode('utf-8')).hexdigest()[:18]}"
        record: OpenAPIToolsetRecord = {
            "toolset_id": toolset_id,
            "created_at": _now(),
            "publisher_id": publisher_id,
            "source_id": source_id,
            "title": title.strip() or "OpenAPI toolset",
            "selected_operations": list(selected_operations),
            "tool_name_prefix": tool_name_prefix.strip(),
            "metadata": dict(metadata or {}),
        }

        if not self.db_path:
            self._memory_toolsets[toolset_id] = record
            return record

        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO purecipher_openapi_toolsets
              (toolset_id, created_at, publisher_id, source_id, title,
               selected_operations_json, tool_name_prefix, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                toolset_id,
                record["created_at"],
                record["publisher_id"],
                record["source_id"],
                record["title"],
                json.dumps(record["selected_operations"]),
                record["tool_name_prefix"],
                json.dumps(record["metadata"]),
            ),
        )
        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return record

    def get_source_spec(self, source_id: str) -> dict[str, Any] | None:
        if not self.db_path:
            rec = self._memory_sources.get(source_id)
            return dict(rec.get("spec_json") or {}) if rec else None

        conn = self._connect()
        cur = conn.execute(
            "SELECT spec_json FROM purecipher_openapi_sources WHERE source_id = ?",
            (source_id,),
        )
        row = cur.fetchone()
        if self._shared_conn is None:
            conn.close()
        if not row:
            return None
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def get_toolset(self, toolset_id: str) -> OpenAPIToolsetRecord | None:
        if not self.db_path:
            rec = self._memory_toolsets.get(toolset_id)
            return dict(rec) if rec else None

        conn = self._connect()
        cur = conn.execute(
            """
            SELECT toolset_id, created_at, publisher_id, source_id, title,
                   selected_operations_json, tool_name_prefix, metadata_json
            FROM purecipher_openapi_toolsets
            WHERE toolset_id = ?
            """,
            (toolset_id,),
        )
        row = cur.fetchone()
        if self._shared_conn is None:
            conn.close()
        if not row:
            return None
        (
            tid,
            created_at,
            publisher_id,
            source_id,
            title,
            selected_json,
            tool_name_prefix,
            metadata_json,
        ) = row
        try:
            selected = json.loads(selected_json)
        except json.JSONDecodeError:
            selected = []
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        return {
            "toolset_id": str(tid),
            "created_at": float(created_at),
            "publisher_id": str(publisher_id),
            "source_id": str(source_id),
            "title": str(title),
            "selected_operations": [str(x) for x in selected] if isinstance(selected, list) else [],
            "tool_name_prefix": str(tool_name_prefix),
            "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        }

    def list_toolsets(self, *, limit: int = 200) -> list[OpenAPIToolsetRecord]:
        if limit <= 0:
            return []
        if not self.db_path:
            items = list(self._memory_toolsets.values())
            items.sort(key=lambda x: float(x.get("created_at", 0.0)), reverse=True)
            return [dict(item) for item in items[:limit]]

        conn = self._connect()
        cur = conn.execute(
            """
            SELECT toolset_id, created_at, publisher_id, source_id, title,
                   selected_operations_json, tool_name_prefix, metadata_json
            FROM purecipher_openapi_toolsets
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        if self._shared_conn is None:
            conn.close()

        out: list[OpenAPIToolsetRecord] = []
        for row in rows:
            (
                tid,
                created_at,
                publisher_id,
                source_id,
                title,
                selected_json,
                tool_name_prefix,
                metadata_json,
            ) = row
            try:
                selected = json.loads(selected_json)
            except json.JSONDecodeError:
                selected = []
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
            out.append(
                {
                    "toolset_id": str(tid),
                    "created_at": float(created_at),
                    "publisher_id": str(publisher_id),
                    "source_id": str(source_id),
                    "title": str(title),
                    "selected_operations": [str(x) for x in selected]
                    if isinstance(selected, list)
                    else [],
                    "tool_name_prefix": str(tool_name_prefix),
                    "metadata": dict(metadata) if isinstance(metadata, dict) else {},
                }
            )
        return out


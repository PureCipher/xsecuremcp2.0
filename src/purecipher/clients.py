"""Persistent client identity + token store for the PureCipher registry.

Iteration 10 introduces first-class MCP-client identities. Until
this iteration the registry's middleware extracted ``actor_id``
from a redacted access-token prefix — a synthetic string with no
addressable identity behind it. With clients in place, every
governance plane (Policy, Contracts, Consent, Provenance,
Reflexive) can reason about *which* MCP client made a call and
operators can attach trust posture to specific identities rather
than to anonymous traffic.

This module defines:

- :class:`RegistryClient` — stable identity record (UUID, slug,
  display name, owner publisher, status, intended use, metadata).
- :class:`RegistryClientToken` — opaque API token issued to a
  client. The plain secret is returned exactly once at creation;
  the store persists only its SHA-256 hash. A short prefix is kept
  in the clear so the UI can render "pcc_abc123…" identifiers
  without exposing the full token.
- :class:`RegistryClientStore` — SQLite-backed (in-memory fallback)
  persistence for both, with helpers for CRUD + token issue /
  revoke / authenticate flows.

Token format is ``pcc_<14 url-safe random chars>`` so a leaked
token is recognisable at a glance and rotates trivially.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import secrets
import sqlite3
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# Allowed slug alphabet — lowercase ASCII alnum + hyphen, with no
# leading/trailing hyphen and no consecutive hyphens. We slugify
# display_name for an initial proposal but accept curator-supplied
# slugs that match this pattern.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_TOKEN_PREFIX = "pcc_"
_TOKEN_RANDOM_LEN = 14
# Keep the first 8 chars (incl. prefix) visible in lists so the UI
# can render "pcc_abc123…" without exposing the rest.
_TOKEN_VISIBLE_PREFIX_LEN = 8


# Client kind taxonomy. The operator picks the kind that best
# describes what they're registering — purely descriptive, used by
# the UI for filtering / grouping. Granularity is the operator's
# call: "agent" can be one identity per running agent (heavy), one
# per agent application (typical), or one per organization (loose).
CLIENT_KINDS: frozenset[str] = frozenset(
    {"agent", "service", "framework", "tooling", "other"}
)


@dataclass(frozen=True)
class RegistryClient:
    """A registered MCP client identity.

    Attributes:
        client_id: Stable UUID assigned at creation.
        slug: Lowercase URL-safe identifier (unique). Either
            curator-supplied or derived from ``display_name``.
        display_name: Human-readable name shown in the UI.
        description: Optional free-text describing the client.
        intended_use: Optional free-text — "what is this client
            going to do with the registry's tools?".
        kind: Taxonomy bucket — ``agent`` (LLM-driven, e.g. Claude
            Desktop), ``service`` (backend bot / non-LLM consumer),
            ``framework`` (orchestration layer like LangGraph),
            ``tooling`` (CI / dev scripts), or ``other``.
        owner_publisher_id: The publisher slug that owns this
            client. Tied to the user who created it.
        status: ``"active"`` (default) or ``"suspended"``.
        suspended_reason: Operator-supplied reason when suspended.
        created_at: UNIX timestamp.
        updated_at: UNIX timestamp.
        metadata: Arbitrary operator-supplied data.
    """

    client_id: str
    slug: str
    display_name: str
    description: str
    intended_use: str
    owner_publisher_id: str
    kind: str = "agent"
    status: str = "active"
    suspended_reason: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "slug": self.slug,
            "display_name": self.display_name,
            "description": self.description,
            "intended_use": self.intended_use,
            "kind": self.kind,
            "owner_publisher_id": self.owner_publisher_id,
            "status": self.status,
            "suspended_reason": self.suspended_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RegistryClientToken:
    """An issued API token for a client.

    The plaintext secret is *not* stored. Only the SHA-256 hash and
    a short visible prefix are persisted; the secret is returned to
    the issuer exactly once at creation.

    Attributes:
        token_id: Stable UUID assigned at creation.
        client_id: Owning client.
        name: Operator-supplied label (e.g. "production deploy").
        secret_hash: SHA-256 hex digest of the full secret.
        secret_prefix: First few chars of the secret in the clear,
            for visual identification in the tokens table.
        created_by: Username of the user who issued the token.
        created_at: UNIX timestamp.
        revoked_at: Optional UNIX timestamp; when set, the token
            no longer authenticates.
        last_used_at: Most recent successful authentication, or
            ``None`` if never used.
    """

    token_id: str
    client_id: str
    name: str
    secret_hash: str
    secret_prefix: str
    created_by: str
    created_at: float
    revoked_at: float | None = None
    last_used_at: float | None = None

    def is_active(self) -> bool:
        return self.revoked_at is None

    def to_dict(self, *, include_hash: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "token_id": self.token_id,
            "client_id": self.client_id,
            "name": self.name,
            "secret_prefix": self.secret_prefix,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
            "active": self.is_active(),
        }
        if include_hash:
            payload["secret_hash"] = self.secret_hash
        return payload


# ── Helpers ────────────────────────────────────────────────────────


def slugify_client(text: str) -> str:
    """Project a free-text display name to a slug.

    Lowercase, ASCII alnum + hyphen, max 63 chars. Returns ``""``
    when the input has no usable characters — caller is expected to
    detect this and supply a slug explicitly.
    """
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    cleaned = cleaned.strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned[:63]


def is_valid_slug(slug: str) -> bool:
    return bool(slug) and bool(_SLUG_RE.match(slug)) and len(slug) <= 63


def generate_token_secret() -> tuple[str, str, str]:
    """Generate a fresh ``(secret, secret_hash, secret_prefix)`` triple.

    The secret is returned to the caller exactly once; only the
    hash + visible prefix are ever persisted.
    """
    body = secrets.token_urlsafe(_TOKEN_RANDOM_LEN)[:_TOKEN_RANDOM_LEN]
    secret = f"{_TOKEN_PREFIX}{body}"
    secret_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    secret_prefix = secret[:_TOKEN_VISIBLE_PREFIX_LEN]
    return secret, secret_hash, secret_prefix


def hash_token_secret(secret: str) -> str:
    """Stable SHA-256 hex digest of a presented secret.

    Used by :meth:`RegistryClientStore.authenticate_token` to look
    a presented bearer token up against the stored hash.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


# ── Errors ─────────────────────────────────────────────────────────


class ClientStoreError(RuntimeError):
    """Raised for client-store conflicts (e.g. duplicate slugs)."""


# ── Store ──────────────────────────────────────────────────────────


class RegistryClientStore:
    """Persistent store for MCP client identities + their tokens.

    Mirrors the pattern used by other PureCipher persistence
    helpers: SQLite when ``db_path`` is set (excluding the
    ``:memory:`` sentinel which the registry uses to mean "no real
    persistence"), in-memory dict otherwise.

    Args:
        db_path: SQLite file path or ``None`` for in-memory mode.
        ensure_schema: When ``True`` (default), create the tables on
            construction. Pass ``False`` when migrations manage the
            schema (the registry detects this via
            ``schema_managed_by_migrations``).
    """

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        if db_path == ":memory:":
            db_path = None
        self._db_path = db_path
        self._memory_clients: dict[str, RegistryClient] = {}
        self._memory_tokens: dict[str, RegistryClientToken] = {}
        if self._db_path and ensure_schema:
            self._ensure_sqlite()

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purecipher_registry_clients (
                    client_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    intended_use TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'agent',
                    owner_publisher_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    suspended_reason TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purecipher_registry_client_tokens (
                    token_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    secret_hash TEXT NOT NULL UNIQUE,
                    secret_prefix TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    revoked_at REAL,
                    last_used_at REAL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ── Client CRUD ────────────────────────────────────────────────

    def create_client(
        self,
        *,
        display_name: str,
        owner_publisher_id: str,
        slug: str | None = None,
        description: str = "",
        intended_use: str = "",
        kind: str = "agent",
        metadata: dict[str, Any] | None = None,
    ) -> RegistryClient:
        """Insert a fresh client record.

        Raises:
            ValueError: If ``display_name`` is empty, ``slug`` (when
                supplied) is malformed, or no usable slug can be
                derived from the display name.
            ClientStoreError: If the slug is already taken.
        """
        display = display_name.strip()
        if not display:
            raise ValueError("display_name is required")
        if slug is not None:
            slug = slug.strip().lower()
            if not is_valid_slug(slug):
                raise ValueError(
                    f"Invalid slug {slug!r}: must be lowercase URL-safe."
                )
        else:
            slug = slugify_client(display)
            if not slug:
                raise ValueError(
                    "Couldn't derive a slug from display_name; supply "
                    "an explicit slug."
                )

        if self.get_client_by_slug(slug) is not None:
            raise ClientStoreError(
                f"A client with slug {slug!r} already exists."
            )

        kind = (kind or "agent").strip().lower()
        if kind not in CLIENT_KINDS:
            raise ValueError(
                f"Unknown client kind: {kind!r}. "
                f"Expected one of: {sorted(CLIENT_KINDS)}."
            )

        now = time.time()
        record = RegistryClient(
            client_id=str(uuid.uuid4()),
            slug=slug,
            display_name=display,
            description=description.strip(),
            intended_use=intended_use.strip(),
            owner_publisher_id=owner_publisher_id.strip() or "unknown",
            kind=kind,
            status="active",
            suspended_reason="",
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self._save_client(record)
        return record

    def get_client(self, client_id: str) -> RegistryClient | None:
        if not self._db_path:
            return self._memory_clients.get(client_id)
        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM purecipher_registry_clients WHERE client_id = ?",
                (client_id,),
            )
            row = cur.fetchone()
            cols = [d[0] for d in cur.description] if cur.description else []
        finally:
            conn.close()
        return _row_to_client(row, cols) if row else None

    def get_client_by_slug(self, slug: str) -> RegistryClient | None:
        if not self._db_path:
            for record in self._memory_clients.values():
                if record.slug == slug:
                    return record
            return None
        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM purecipher_registry_clients WHERE slug = ?",
                (slug,),
            )
            row = cur.fetchone()
            cols = [d[0] for d in cur.description] if cur.description else []
        finally:
            conn.close()
        return _row_to_client(row, cols) if row else None

    def list_clients(
        self,
        *,
        owner_publisher_id: str | None = None,
        limit: int = 200,
    ) -> list[RegistryClient]:
        """List clients, optionally scoped to a single owner.

        Sorted most-recently-updated first.
        """
        if not self._db_path:
            records = list(self._memory_clients.values())
            if owner_publisher_id is not None:
                records = [
                    r
                    for r in records
                    if r.owner_publisher_id == owner_publisher_id
                ]
            records.sort(key=lambda r: r.updated_at, reverse=True)
            return records[:limit]

        conn = sqlite3.connect(self._db_path)
        try:
            if owner_publisher_id is not None:
                cur = conn.execute(
                    """
                    SELECT * FROM purecipher_registry_clients
                    WHERE owner_publisher_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (owner_publisher_id, int(limit)),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT * FROM purecipher_registry_clients
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
        finally:
            conn.close()
        return [_row_to_client(r, cols) for r in rows]

    def update_client(
        self,
        client_id: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        intended_use: str | None = None,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegistryClient | None:
        """Patch updatable fields. Returns the new record or
        ``None`` if the client doesn't exist."""
        existing = self.get_client(client_id)
        if existing is None:
            return None
        merged_metadata = dict(existing.metadata)
        if metadata is not None:
            merged_metadata.update(metadata)
        if kind is not None and kind not in CLIENT_KINDS:
            raise ClientStoreError(
                f"Unknown client kind: {kind!r}. "
                f"Allowed: {sorted(CLIENT_KINDS)}"
            )
        updated = RegistryClient(
            client_id=existing.client_id,
            slug=existing.slug,
            display_name=(
                display_name.strip()
                if display_name is not None
                else existing.display_name
            ),
            description=(
                description.strip()
                if description is not None
                else existing.description
            ),
            intended_use=(
                intended_use.strip()
                if intended_use is not None
                else existing.intended_use
            ),
            kind=kind if kind is not None else existing.kind,
            owner_publisher_id=existing.owner_publisher_id,
            status=existing.status,
            suspended_reason=existing.suspended_reason,
            created_at=existing.created_at,
            updated_at=time.time(),
            metadata=merged_metadata,
        )
        self._save_client(updated)
        return updated

    def set_status(
        self,
        client_id: str,
        *,
        status: str,
        reason: str = "",
    ) -> RegistryClient | None:
        if status not in ("active", "suspended"):
            raise ValueError(f"Unknown client status: {status!r}")
        existing = self.get_client(client_id)
        if existing is None:
            return None
        updated = RegistryClient(
            client_id=existing.client_id,
            slug=existing.slug,
            display_name=existing.display_name,
            description=existing.description,
            intended_use=existing.intended_use,
            kind=existing.kind,
            owner_publisher_id=existing.owner_publisher_id,
            status=status,
            suspended_reason=(
                reason.strip() if status == "suspended" else ""
            ),
            created_at=existing.created_at,
            updated_at=time.time(),
            metadata=dict(existing.metadata),
        )
        self._save_client(updated)
        return updated

    def _save_client(self, record: RegistryClient) -> None:
        if not self._db_path:
            self._memory_clients[record.client_id] = record
            return
        import json

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO purecipher_registry_clients (
                    client_id, slug, display_name, description,
                    intended_use, kind, owner_publisher_id, status,
                    suspended_reason, created_at, updated_at,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    slug = excluded.slug,
                    display_name = excluded.display_name,
                    description = excluded.description,
                    intended_use = excluded.intended_use,
                    kind = excluded.kind,
                    owner_publisher_id = excluded.owner_publisher_id,
                    status = excluded.status,
                    suspended_reason = excluded.suspended_reason,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record.client_id,
                    record.slug,
                    record.display_name,
                    record.description,
                    record.intended_use,
                    record.kind,
                    record.owner_publisher_id,
                    record.status,
                    record.suspended_reason,
                    record.created_at,
                    record.updated_at,
                    json.dumps(record.metadata, sort_keys=True),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Tokens ──────────────────────────────────────────────────────

    def issue_token(
        self,
        *,
        client_id: str,
        name: str,
        created_by: str,
    ) -> tuple[RegistryClientToken, str]:
        """Mint a new token for the client.

        Returns ``(token_record, plaintext_secret)``. The plaintext
        is the only place the full secret will exist after this
        method returns — only the hash + visible prefix are
        persisted.

        Raises ``ClientStoreError`` when the client doesn't exist
        or is suspended.
        """
        client = self.get_client(client_id)
        if client is None:
            raise ClientStoreError(f"Client {client_id!r} not found.")
        if client.status != "active":
            raise ClientStoreError(
                f"Cannot issue tokens for non-active client {client_id!r} "
                f"(status: {client.status})."
            )

        name = name.strip() or "Default"
        secret, secret_hash, secret_prefix = generate_token_secret()
        token = RegistryClientToken(
            token_id=str(uuid.uuid4()),
            client_id=client_id,
            name=name,
            secret_hash=secret_hash,
            secret_prefix=secret_prefix,
            created_by=created_by.strip() or "unknown",
            created_at=time.time(),
            revoked_at=None,
            last_used_at=None,
        )
        self._save_token(token)
        return token, secret

    def list_tokens(
        self,
        client_id: str,
        *,
        include_revoked: bool = True,
    ) -> list[RegistryClientToken]:
        if not self._db_path:
            tokens = [
                t for t in self._memory_tokens.values() if t.client_id == client_id
            ]
            if not include_revoked:
                tokens = [t for t in tokens if t.revoked_at is None]
            tokens.sort(key=lambda t: t.created_at, reverse=True)
            return tokens

        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                """
                SELECT * FROM purecipher_registry_client_tokens
                WHERE client_id = ?
                ORDER BY created_at DESC
                """,
                (client_id,),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
        finally:
            conn.close()
        tokens = [_row_to_token(r, cols) for r in rows]
        if not include_revoked:
            tokens = [t for t in tokens if t.revoked_at is None]
        return tokens

    def revoke_token(self, token_id: str) -> RegistryClientToken | None:
        existing = self._get_token(token_id)
        if existing is None:
            return None
        if existing.revoked_at is not None:
            return existing
        revoked = RegistryClientToken(
            token_id=existing.token_id,
            client_id=existing.client_id,
            name=existing.name,
            secret_hash=existing.secret_hash,
            secret_prefix=existing.secret_prefix,
            created_by=existing.created_by,
            created_at=existing.created_at,
            revoked_at=time.time(),
            last_used_at=existing.last_used_at,
        )
        self._save_token(revoked)
        return revoked

    def authenticate_token(
        self, presented_secret: str
    ) -> tuple[RegistryClient, RegistryClientToken] | None:
        """Resolve a presented bearer token to its client record.

        Returns ``(client, token)`` on success and updates the
        token's ``last_used_at`` timestamp. Returns ``None`` when
        the token doesn't match, was revoked, or its client is
        suspended.
        """
        if not presented_secret or not presented_secret.startswith(_TOKEN_PREFIX):
            return None
        secret_hash = hash_token_secret(presented_secret)

        token = self._get_token_by_hash(secret_hash)
        if token is None or token.revoked_at is not None:
            return None
        client = self.get_client(token.client_id)
        if client is None or client.status != "active":
            return None

        # Update last_used_at — best-effort; failures here shouldn't
        # block the authentication.
        with contextlib.suppress(Exception):
            self._mark_token_used(token.token_id)
        return client, token

    def _get_token(self, token_id: str) -> RegistryClientToken | None:
        if not self._db_path:
            return self._memory_tokens.get(token_id)
        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM purecipher_registry_client_tokens WHERE token_id = ?",
                (token_id,),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
        finally:
            conn.close()
        return _row_to_token(row, cols) if row else None

    def _get_token_by_hash(self, secret_hash: str) -> RegistryClientToken | None:
        if not self._db_path:
            for token in self._memory_tokens.values():
                if token.secret_hash == secret_hash:
                    return token
            return None
        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM purecipher_registry_client_tokens WHERE secret_hash = ?",
                (secret_hash,),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
        finally:
            conn.close()
        return _row_to_token(row, cols) if row else None

    def _mark_token_used(self, token_id: str) -> None:
        if not self._db_path:
            existing = self._memory_tokens.get(token_id)
            if existing is None:
                return
            self._memory_tokens[token_id] = RegistryClientToken(
                token_id=existing.token_id,
                client_id=existing.client_id,
                name=existing.name,
                secret_hash=existing.secret_hash,
                secret_prefix=existing.secret_prefix,
                created_by=existing.created_by,
                created_at=existing.created_at,
                revoked_at=existing.revoked_at,
                last_used_at=time.time(),
            )
            return
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "UPDATE purecipher_registry_client_tokens SET last_used_at = ? WHERE token_id = ?",
                (time.time(), token_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _save_token(self, token: RegistryClientToken) -> None:
        if not self._db_path:
            self._memory_tokens[token.token_id] = token
            return
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO purecipher_registry_client_tokens (
                    token_id, client_id, name, secret_hash, secret_prefix,
                    created_by, created_at, revoked_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(token_id) DO UPDATE SET
                    name = excluded.name,
                    revoked_at = excluded.revoked_at,
                    last_used_at = excluded.last_used_at
                """,
                (
                    token.token_id,
                    token.client_id,
                    token.name,
                    token.secret_hash,
                    token.secret_prefix,
                    token.created_by,
                    token.created_at,
                    token.revoked_at,
                    token.last_used_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def _row_to_client(row: Any, cols: Iterable[str]) -> RegistryClient:
    import json

    record = dict(zip(cols, row, strict=False))
    metadata_raw = record.get("metadata_json") or "{}"
    try:
        metadata = json.loads(metadata_raw)
    except Exception:
        metadata = {}
    return RegistryClient(
        client_id=str(record["client_id"]),
        slug=str(record["slug"]),
        display_name=str(record["display_name"]),
        description=str(record["description"] or ""),
        intended_use=str(record["intended_use"] or ""),
        kind=str(record.get("kind") or "agent"),
        owner_publisher_id=str(record["owner_publisher_id"] or ""),
        status=str(record["status"] or "active"),
        suspended_reason=str(record["suspended_reason"] or ""),
        created_at=float(record["created_at"] or 0.0),
        updated_at=float(record["updated_at"] or 0.0),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _row_to_token(row: Any, cols: Iterable[str]) -> RegistryClientToken:
    record = dict(zip(cols, row, strict=False))
    return RegistryClientToken(
        token_id=str(record["token_id"]),
        client_id=str(record["client_id"]),
        name=str(record["name"] or ""),
        secret_hash=str(record["secret_hash"]),
        secret_prefix=str(record["secret_prefix"] or ""),
        created_by=str(record["created_by"] or ""),
        created_at=float(record["created_at"] or 0.0),
        revoked_at=(
            float(record["revoked_at"]) if record.get("revoked_at") is not None else None
        ),
        last_used_at=(
            float(record["last_used_at"])
            if record.get("last_used_at") is not None
            else None
        ),
    )


__all__ = [
    "ClientStoreError",
    "RegistryClient",
    "RegistryClientStore",
    "RegistryClientToken",
    "generate_token_secret",
    "hash_token_secret",
    "is_valid_slug",
    "slugify_client",
]

"""Writable account security storage for the PureCipher registry UI."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from purecipher.auth import RegistryRole, RegistryUser

_PBKDF2_ITERATIONS = 210_000
_TOKEN_PREFIX = "pcat_"


@dataclass(frozen=True)
class RegistrySessionRecord:
    session_id: str
    username: str
    role: RegistryRole
    display_name: str
    created_at: float
    expires_at: float
    revoked_at: float | None = None


def _now() -> float:
    return time.time()


def _iso(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def _hash_password(password: str, *, salt: str | None = None) -> str:
    resolved_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        resolved_salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${resolved_salt}${digest}"


def _verify_password(password: str, password_hash: str) -> bool:
    parts = password_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt = parts[2]
    expected = parts[3]
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RegistryAccountSecurityStore:
    """Persistent accounts, revocable sessions, and personal API tokens."""

    def __init__(
        self,
        db_path: str | None,
        seed_users: tuple[RegistryUser, ...],
        *,
        ensure_schema: bool = True,
    ) -> None:
        self._db_path = db_path
        self._memory_accounts: dict[str, dict[str, Any]] = {}
        self._memory_sessions: dict[str, dict[str, Any]] = {}
        self._memory_tokens: dict[str, dict[str, Any]] = {}
        if self._db_path and ensure_schema:
            self._ensure_sqlite()
        self.seed_users(seed_users)

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_accounts (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL,
                created_at REAL,
                disabled_at REAL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purecipher_registry_api_tokens (
                token_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used_at REAL,
                revoked_at REAL
            );
            """
        )
        conn.commit()
        for statement in (
            "ALTER TABLE purecipher_registry_accounts ADD COLUMN created_at REAL",
            "ALTER TABLE purecipher_registry_accounts ADD COLUMN disabled_at REAL",
        ):
            with suppress(sqlite3.OperationalError):
                conn.execute(statement)
        conn.execute(
            "UPDATE purecipher_registry_accounts SET created_at = updated_at WHERE created_at IS NULL"
        )
        conn.commit()
        conn.close()

    def seed_users(self, users: tuple[RegistryUser, ...]) -> None:
        for user in users:
            if self._get_account(user.username) is not None:
                continue
            self._save_account(
                username=user.username,
                password_hash=_hash_password(user.password),
                role=user.role,
                display_name=user.display_name,
                source="seed",
            )

    def has_accounts(self) -> bool:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute("SELECT 1 FROM purecipher_registry_accounts LIMIT 1")
            has_account = cur.fetchone() is not None
            conn.close()
            return has_account
        return bool(self._memory_accounts)

    def create_bootstrap_admin(
        self,
        *,
        username: str,
        password: str,
        display_name: str,
    ) -> RegistryUser | None:
        username = username.strip()
        display_name = display_name.strip() or "Registry Admin"
        if not username or not password or self.has_accounts():
            return None
        user = RegistryUser(
            username=username,
            password="",
            role=RegistryRole.ADMIN,
            display_name=display_name,
        )
        self._save_account(
            username=username,
            password_hash=_hash_password(password),
            role=RegistryRole.ADMIN,
            display_name=display_name,
            source="bootstrap",
        )
        return user

    def authenticate(self, username: str, password: str) -> RegistryUser | None:
        account = self._get_account(username)
        if account is None:
            return None
        if account.get("disabled_at") is not None:
            return None
        if not _verify_password(password, str(account["password_hash"])):
            return None
        return RegistryUser(
            username=str(account["username"]),
            password="",
            role=RegistryRole(str(account["role"])),
            display_name=str(account["display_name"]),
        )

    def change_password(
        self,
        *,
        username: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        account = self._get_account(username)
        if account is None:
            return False
        if not _verify_password(current_password, str(account["password_hash"])):
            return False
        self._save_account(
            username=username,
            password_hash=_hash_password(new_password),
            role=RegistryRole(str(account["role"])),
            display_name=str(account["display_name"]),
            source=str(account.get("source") or "local"),
        )
        self.revoke_sessions_for_user(username=username)
        return True

    def list_accounts(self) -> list[dict[str, Any]]:
        rows = self._list_account_rows()
        return [self._serialize_account(row) for row in rows]

    def create_account(
        self,
        *,
        username: str,
        password: str,
        role: RegistryRole,
        display_name: str,
    ) -> dict[str, Any] | None:
        username = username.strip()
        display_name = display_name.strip() or username
        if not username or not password or self._get_account(username) is not None:
            return None
        self._save_account(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            display_name=display_name,
            source="admin",
        )
        account = self._get_account(username)
        return self._serialize_account(account) if account is not None else None

    def update_account(
        self,
        *,
        username: str,
        role: RegistryRole | None = None,
        display_name: str | None = None,
        disabled: bool | None = None,
    ) -> dict[str, Any] | None:
        account = self._get_account(username)
        if account is None:
            return None
        current_disabled = account.get("disabled_at")
        current_role = RegistryRole(str(account["role"]))
        disabled_at = current_disabled
        if disabled is True and current_disabled is None:
            disabled_at = _now()
        elif disabled is False:
            disabled_at = None
        self._save_account(
            username=str(account["username"]),
            password_hash=str(account["password_hash"]),
            role=role or current_role,
            display_name=(
                display_name.strip()
                if display_name is not None
                else str(account["display_name"])
            )
            or str(account["username"]),
            source=str(account.get("source") or "local"),
            created_at=float(account.get("created_at") or account.get("updated_at") or _now()),
            disabled_at=disabled_at,
        )
        if disabled is True or (role is not None and role != current_role):
            self.revoke_sessions_for_user(username=username)
            self.revoke_api_tokens_for_user(username=username)
        refreshed = self._get_account(username)
        return self._serialize_account(refreshed) if refreshed is not None else None

    def reset_password(self, *, username: str, new_password: str) -> bool:
        account = self._get_account(username)
        if account is None or not new_password:
            return False
        self._save_account(
            username=str(account["username"]),
            password_hash=_hash_password(new_password),
            role=RegistryRole(str(account["role"])),
            display_name=str(account["display_name"]),
            source=str(account.get("source") or "local"),
            created_at=float(account.get("created_at") or account.get("updated_at") or _now()),
            disabled_at=account.get("disabled_at"),
        )
        self.revoke_sessions_for_user(username=username)
        self.revoke_api_tokens_for_user(username=username)
        return True

    def create_session(
        self,
        *,
        user: RegistryUser,
        ttl_seconds: int,
    ) -> RegistrySessionRecord:
        now = _now()
        record = {
            "session_id": secrets.token_urlsafe(18),
            "username": user.username,
            "role": user.role.value,
            "display_name": user.display_name,
            "created_at": now,
            "expires_at": now + ttl_seconds,
            "revoked_at": None,
        }
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO purecipher_registry_sessions "
                "(session_id, username, role, display_name, created_at, expires_at, revoked_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["session_id"],
                    record["username"],
                    record["role"],
                    record["display_name"],
                    record["created_at"],
                    record["expires_at"],
                    record["revoked_at"],
                ),
            )
            conn.commit()
            conn.close()
        else:
            self._memory_sessions[str(record["session_id"])] = record
        return _session_record(record)

    def session_is_active(self, session_id: str, *, username: str) -> bool:
        if not session_id:
            return True
        record = self._get_session(session_id)
        if record is None:
            return False
        return (
            str(record["username"]) == username
            and record.get("revoked_at") is None
            and float(record["expires_at"]) > _now()
        )

    def revoke_session(self, *, session_id: str, username: str) -> bool:
        record = self._get_session(session_id)
        if record is None or str(record["username"]) != username:
            return False
        return self._revoke_session_id(session_id)

    def revoke_sessions_for_user(
        self,
        *,
        username: str,
        except_session_id: str | None = None,
    ) -> int:
        records = self._list_session_rows(username=username, limit=500)
        count = 0
        for record in records:
            session_id = str(record["session_id"])
            if except_session_id and session_id == except_session_id:
                continue
            if record.get("revoked_at") is None and self._revoke_session_id(session_id):
                count += 1
        return count

    def list_sessions(self, *, username: str, limit: int = 20) -> list[dict[str, Any]]:
        return [
            {
                "session_id": str(row["session_id"]),
                "username": str(row["username"]),
                "role": str(row["role"]),
                "display_name": str(row["display_name"]),
                "created_at": _iso(float(row["created_at"])),
                "expires_at": _iso(float(row["expires_at"])),
                "revoked_at": _iso(float(row["revoked_at"]))
                if row.get("revoked_at") is not None
                else None,
                "active": row.get("revoked_at") is None and float(row["expires_at"]) > _now(),
            }
            for row in self._list_session_rows(username=username, limit=limit)
        ]

    def create_api_token(self, *, username: str, name: str) -> dict[str, Any]:
        account = self._get_account(username)
        if account is None:
            raise ValueError("Unknown user.")
        token_id = "tok_" + secrets.token_urlsafe(10)
        token = _TOKEN_PREFIX + secrets.token_urlsafe(32)
        now = _now()
        record = {
            "token_id": token_id,
            "token_hash": _hash_token(token),
            "username": username,
            "name": name.strip() or "Registry API token",
            "role": str(account["role"]),
            "display_name": str(account["display_name"]),
            "created_at": now,
            "last_used_at": None,
            "revoked_at": None,
        }
        self._save_token(record)
        return {"token": token, "token_record": self._serialize_token(record)}

    def list_api_tokens(self, *, username: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._list_token_rows(username=username, limit=limit)
        return [self._serialize_token(row) for row in rows]

    def revoke_api_token(self, *, username: str, token_id: str) -> bool:
        rows = self._list_token_rows(username=username, limit=500)
        if not any(str(row["token_id"]) == token_id for row in rows):
            return False
        now = _now()
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE purecipher_registry_api_tokens SET revoked_at = ? WHERE token_id = ? AND username = ?",
                (now, token_id, username),
            )
            changed = conn.total_changes > 0
            conn.commit()
            conn.close()
            return changed
        record = self._memory_tokens.get(token_id)
        if record is None:
            return False
        record["revoked_at"] = now
        return True

    def revoke_api_tokens_for_user(self, *, username: str) -> int:
        rows = self._list_token_rows(username=username, limit=500)
        count = 0
        now = _now()
        for row in rows:
            if row.get("revoked_at") is not None:
                continue
            token_id = str(row["token_id"])
            if self._db_path:
                conn = sqlite3.connect(self._db_path)
                conn.execute(
                    "UPDATE purecipher_registry_api_tokens SET revoked_at = ? WHERE token_id = ? AND username = ? AND revoked_at IS NULL",
                    (now, token_id, username),
                )
                changed = conn.total_changes > 0
                conn.commit()
                conn.close()
                if changed:
                    count += 1
            else:
                record = self._memory_tokens.get(token_id)
                if record is not None and record.get("revoked_at") is None:
                    record["revoked_at"] = now
                    count += 1
        return count

    def authenticate_api_token(self, token: str) -> RegistryUser | None:
        if not token.startswith(_TOKEN_PREFIX):
            return None
        token_hash = _hash_token(token)
        record = self._get_token_by_hash(token_hash)
        if record is None or record.get("revoked_at") is not None:
            return None
        now = _now()
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE purecipher_registry_api_tokens SET last_used_at = ? WHERE token_id = ?",
                (now, record["token_id"]),
            )
            conn.commit()
            conn.close()
        else:
            record["last_used_at"] = now
        return RegistryUser(
            username=str(record["username"]),
            password="",
            role=RegistryRole(str(record["role"])),
            display_name=str(record["display_name"]),
        )

    def _get_account(self, username: str) -> dict[str, Any] | None:
        key = username.strip()
        if not key:
            return None
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT username, password_hash, role, display_name, source, updated_at, created_at, disabled_at "
                "FROM purecipher_registry_accounts WHERE username = ?",
                (key,),
            )
            row = cur.fetchone()
            conn.close()
            if row is None:
                return None
            username_v, password_hash, role, display_name, source, updated_at, created_at, disabled_at = row
            return {
                "username": username_v,
                "password_hash": password_hash,
                "role": role,
                "display_name": display_name,
                "source": source,
                "updated_at": updated_at,
                "created_at": created_at,
                "disabled_at": disabled_at,
            }
        return self._memory_accounts.get(key)

    def _save_account(
        self,
        *,
        username: str,
        password_hash: str,
        role: RegistryRole,
        display_name: str,
        source: str,
        created_at: float | None = None,
        disabled_at: float | None = None,
    ) -> None:
        now = _now()
        resolved_created_at = created_at if created_at is not None else now
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """
                INSERT INTO purecipher_registry_accounts
                    (username, password_hash, role, display_name, source, updated_at, created_at, disabled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    display_name = excluded.display_name,
                    source = excluded.source,
                    updated_at = excluded.updated_at,
                    created_at = COALESCE(purecipher_registry_accounts.created_at, excluded.created_at),
                    disabled_at = excluded.disabled_at
                """,
                (
                    username,
                    password_hash,
                    role.value,
                    display_name,
                    source,
                    now,
                    resolved_created_at,
                    disabled_at,
                ),
            )
            conn.commit()
            conn.close()
            return
        self._memory_accounts[username] = {
            "username": username,
            "password_hash": password_hash,
            "role": role.value,
            "display_name": display_name,
            "source": source,
            "updated_at": now,
            "created_at": resolved_created_at,
            "disabled_at": disabled_at,
        }

    def _list_account_rows(self) -> list[dict[str, Any]]:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT username, password_hash, role, display_name, source, updated_at, created_at, disabled_at "
                "FROM purecipher_registry_accounts ORDER BY username ASC"
            )
            rows = [_account_row(row) for row in cur.fetchall()]
            conn.close()
            return rows
        return [
            dict(row)
            for row in sorted(
                self._memory_accounts.values(),
                key=lambda item: str(item["username"]),
            )
        ]

    def _get_session(self, session_id: str) -> dict[str, Any] | None:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT session_id, username, role, display_name, created_at, expires_at, revoked_at "
                "FROM purecipher_registry_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            conn.close()
            return _session_row(row) if row is not None else None
        return self._memory_sessions.get(session_id)

    def _revoke_session_id(self, session_id: str) -> bool:
        now = _now()
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE purecipher_registry_sessions SET revoked_at = ? WHERE session_id = ? AND revoked_at IS NULL",
                (now, session_id),
            )
            changed = conn.total_changes > 0
            conn.commit()
            conn.close()
            return changed
        record = self._memory_sessions.get(session_id)
        if record is None or record.get("revoked_at") is not None:
            return False
        record["revoked_at"] = now
        return True

    def _list_session_rows(self, *, username: str, limit: int) -> list[dict[str, Any]]:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT session_id, username, role, display_name, created_at, expires_at, revoked_at "
                "FROM purecipher_registry_sessions WHERE username = ? ORDER BY created_at DESC LIMIT ?",
                (username, limit),
            )
            rows = [_session_row(row) for row in cur.fetchall()]
            conn.close()
            return rows
        return [
            dict(row)
            for row in sorted(
                self._memory_sessions.values(),
                key=lambda item: float(item["created_at"]),
                reverse=True,
            )
            if row["username"] == username
        ][:limit]

    def _save_token(self, record: dict[str, Any]) -> None:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO purecipher_registry_api_tokens "
                "(token_id, token_hash, username, name, role, display_name, created_at, last_used_at, revoked_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["token_id"],
                    record["token_hash"],
                    record["username"],
                    record["name"],
                    record["role"],
                    record["display_name"],
                    record["created_at"],
                    record["last_used_at"],
                    record["revoked_at"],
                ),
            )
            conn.commit()
            conn.close()
            return
        self._memory_tokens[str(record["token_id"])] = record

    def _list_token_rows(self, *, username: str, limit: int) -> list[dict[str, Any]]:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT token_id, token_hash, username, name, role, display_name, created_at, last_used_at, revoked_at "
                "FROM purecipher_registry_api_tokens WHERE username = ? ORDER BY created_at DESC LIMIT ?",
                (username, limit),
            )
            rows = [_token_row(row) for row in cur.fetchall()]
            conn.close()
            return rows
        return [
            dict(row)
            for row in sorted(
                self._memory_tokens.values(),
                key=lambda item: float(item["created_at"]),
                reverse=True,
            )
            if row["username"] == username
        ][:limit]

    def _get_token_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute(
                "SELECT token_id, token_hash, username, name, role, display_name, created_at, last_used_at, revoked_at "
                "FROM purecipher_registry_api_tokens WHERE token_hash = ?",
                (token_hash,),
            )
            row = cur.fetchone()
            conn.close()
            return _token_row(row) if row is not None else None
        for row in self._memory_tokens.values():
            if hmac.compare_digest(str(row["token_hash"]), token_hash):
                return row
        return None

    def _serialize_token(self, row: dict[str, Any]) -> dict[str, Any]:
        token_id = str(row["token_id"])
        return {
            "token_id": token_id,
            "name": str(row["name"]),
            "token_hint": f"{_TOKEN_PREFIX}...{token_id[-6:]}",
            "created_at": _iso(float(row["created_at"])),
            "last_used_at": _iso(float(row["last_used_at"]))
            if row.get("last_used_at") is not None
            else None,
            "revoked_at": _iso(float(row["revoked_at"]))
            if row.get("revoked_at") is not None
            else None,
            "active": row.get("revoked_at") is None,
        }

    def _serialize_account(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if row is None:
            return {}
        disabled_at = row.get("disabled_at")
        return {
            "username": str(row["username"]),
            "role": str(row["role"]),
            "display_name": str(row["display_name"]),
            "source": str(row.get("source") or "local"),
            "created_at": _iso(float(row.get("created_at") or row.get("updated_at") or _now())),
            "updated_at": _iso(float(row.get("updated_at") or _now())),
            "disabled_at": _iso(float(disabled_at)) if disabled_at is not None else None,
            "active": disabled_at is None,
        }


def _session_row(row: tuple[Any, ...]) -> dict[str, Any]:
    session_id, username, role, display_name, created_at, expires_at, revoked_at = row
    return {
        "session_id": session_id,
        "username": username,
        "role": role,
        "display_name": display_name,
        "created_at": created_at,
        "expires_at": expires_at,
        "revoked_at": revoked_at,
    }


def _account_row(row: tuple[Any, ...]) -> dict[str, Any]:
    username, password_hash, role, display_name, source, updated_at, created_at, disabled_at = row
    return {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "display_name": display_name,
        "source": source,
        "updated_at": updated_at,
        "created_at": created_at,
        "disabled_at": disabled_at,
    }


def _session_record(row: dict[str, Any]) -> RegistrySessionRecord:
    return RegistrySessionRecord(
        session_id=str(row["session_id"]),
        username=str(row["username"]),
        role=RegistryRole(str(row["role"])),
        display_name=str(row["display_name"]),
        created_at=float(row["created_at"]),
        expires_at=float(row["expires_at"]),
        revoked_at=float(row["revoked_at"]) if row.get("revoked_at") is not None else None,
    )


def _token_row(row: tuple[Any, ...]) -> dict[str, Any]:
    token_id, token_hash, username, name, role, display_name, created_at, last_used_at, revoked_at = row
    return {
        "token_id": token_id,
        "token_hash": token_hash,
        "username": username,
        "name": name,
        "role": role,
        "display_name": display_name,
        "created_at": created_at,
        "last_used_at": last_used_at,
        "revoked_at": revoked_at,
    }


@dataclass
class _LockoutEntry:
    """Internal counter for one (username, ip) tuple."""

    failures: int = 0
    first_failure_at: float = 0.0
    locked_until: float = 0.0


class LoginLockout:
    """Per-(username, ip) login throttle.

    Tracks failed attempts in a sliding window. Once ``max_failures`` is
    reached within ``window_seconds`` the tuple is locked for
    ``lockout_seconds`` and subsequent attempts are rejected until the
    lockout expires.

    Pre-fix the registry had no rate limiting on ``POST /registry/login``,
    making password brute force trivial. This class is in-memory and
    therefore process-local; running multiple registry workers behind a
    load balancer requires a shared backend (Redis, etc.) — out of
    scope for the MVP.

    Args:
        max_failures: Number of failures inside ``window_seconds`` that
            triggers a lockout. Default 10.
        window_seconds: Sliding window for counting failures. Default
            600 (10 minutes).
        lockout_seconds: How long a tuple stays locked after exceeding
            ``max_failures``. Default 900 (15 minutes).
        clock: Optional callable returning the current monotonic time
            in seconds. Tests inject this to avoid sleeping.
    """

    def __init__(
        self,
        *,
        max_failures: int = 10,
        window_seconds: float = 600.0,
        lockout_seconds: float = 900.0,
        clock: Any = None,
    ) -> None:
        self._max = int(max_failures)
        self._window = float(window_seconds)
        self._lockout = float(lockout_seconds)
        self._clock = clock or time.monotonic
        self._entries: dict[tuple[str, str], _LockoutEntry] = {}

    @property
    def max_failures(self) -> int:
        return self._max

    @property
    def lockout_seconds(self) -> float:
        return self._lockout

    @staticmethod
    def _key(username: str, client_ip: str) -> tuple[str, str]:
        return (username.lower().strip(), (client_ip or "").strip())

    def is_locked(self, username: str, client_ip: str) -> tuple[bool, float]:
        """Return ``(locked, retry_after_seconds)``."""
        if not username:
            return (False, 0.0)
        key = self._key(username, client_ip)
        entry = self._entries.get(key)
        if entry is None:
            return (False, 0.0)
        now = self._clock()
        if entry.locked_until > now:
            return (True, max(0.0, entry.locked_until - now))
        return (False, 0.0)

    def register_failure(
        self, username: str, client_ip: str
    ) -> tuple[bool, float, int]:
        """Record a failed attempt.

        Returns ``(now_locked, retry_after_seconds, failures_in_window)``.
        ``now_locked`` is True iff this failure tipped the tuple over
        the threshold.
        """
        if not username:
            return (False, 0.0, 0)
        key = self._key(username, client_ip)
        now = self._clock()
        entry = self._entries.get(key)

        # Already-locked entries don't count further failures; the
        # lockout duration runs to completion and then resets.
        if entry is not None and entry.locked_until > now:
            return (True, entry.locked_until - now, entry.failures)

        # Reset the window if it has elapsed since the first failure.
        if entry is None or (now - entry.first_failure_at) > self._window:
            entry = _LockoutEntry(failures=0, first_failure_at=now)
            self._entries[key] = entry

        entry.failures += 1
        if entry.failures >= self._max:
            entry.locked_until = now + self._lockout
            return (True, self._lockout, entry.failures)
        return (False, 0.0, entry.failures)

    def register_success(self, username: str, client_ip: str) -> None:
        """Clear the failure counter for a successful login."""
        if not username:
            return
        self._entries.pop(self._key(username, client_ip), None)

    def reset(self) -> None:
        """Drop all tracked state. Useful in tests."""
        self._entries.clear()


__all__ = [
    "LoginLockout",
    "RegistryAccountSecurityStore",
    "RegistrySessionRecord",
]

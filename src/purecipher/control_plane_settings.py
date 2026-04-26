"""Persistent settings for runtime control-plane toggles.

Iteration 9 introduces operator-driven runtime toggles for the four
opt-in SecureMCP control planes (Contract Broker, Consent Graph,
Provenance Ledger, Reflexive Core). Toggles take effect immediately
on the running registry — the Iter 9 backend mutates the security
context's plane attribute *and* the middleware chain so enforcement
matches what the panels report. The persisted record here is what
re-applies the toggle on the next startup, so an operator who
disables a plane via the UI doesn't have it spring back to "on" the
next time the process restarts.

The store is intentionally tiny — one row per plane, with the last
actor and timestamp preserved for audit. We use the same SQLite
file the rest of the registry persistence layer uses; in-memory
fallback applies when no ``persistence_path`` is configured.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable


# Canonical plane names. These are the keys used everywhere in the
# Iter 9 surface — keep this set in sync with
# ``PureCipherRegistry.enable_plane`` / ``disable_plane`` and the
# matching admin route's path-param validator.
PLANE_NAMES: frozenset[str] = frozenset(
    {"contracts", "consent", "provenance", "reflexive"}
)


@dataclass(frozen=True)
class ControlPlaneSetting:
    """A single plane's persisted toggle state."""

    plane: str
    enabled: bool
    updated_at: float
    updated_by: str

    def to_dict(self) -> dict:
        return {
            "plane": self.plane,
            "enabled": self.enabled,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
        }


class RegistryControlPlaneStore:
    """Persistent control-plane toggle settings.

    Mirrors the shape of the existing ``RegistryUserPreferenceStore``:
    SQLite-backed when ``db_path`` is set, in-memory otherwise.

    Args:
        db_path: SQLite path, or ``None`` for in-memory.
        ensure_schema: When ``True`` (default), create the table on
            construction. Set ``False`` when migrations manage the
            schema (matches the existing pattern).
    """

    def __init__(self, db_path: str | None, *, ensure_schema: bool = True) -> None:
        # ``:memory:`` is the registry's convention for "no real
        # persistence" — its other settings stores treat it as a
        # signal that the SQLite layer isn't available across
        # connections (each ``sqlite3.connect(":memory:")`` opens a
        # fresh isolated DB). Map it to the in-memory dict mode so
        # we don't confuse callers with sqlite3 errors when the
        # registry happens to be in ephemeral mode.
        if db_path == ":memory:":
            db_path = None
        self._db_path = db_path
        self._memory: dict[str, ControlPlaneSetting] = {}
        if self._db_path and ensure_schema:
            self._ensure_sqlite()

    def _ensure_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purecipher_registry_control_planes (
                    plane TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    updated_by TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> dict[str, ControlPlaneSetting]:
        """Return every persisted plane setting, keyed by plane name.

        Planes that have never been toggled aren't in the result —
        callers should treat absence as "no override, use the
        constructor default."
        """
        if not self._db_path:
            return dict(self._memory)
        conn = sqlite3.connect(self._db_path)
        try:
            cur = conn.execute(
                """
                SELECT plane, enabled, updated_at, updated_by
                FROM purecipher_registry_control_planes
                """
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        result: dict[str, ControlPlaneSetting] = {}
        for row in rows:
            try:
                plane, enabled, updated_at, updated_by = row
            except ValueError:
                continue
            if plane not in PLANE_NAMES:
                # Unknown plane in the store — ignore rather than
                # let stale data confuse the runtime model.
                continue
            result[str(plane)] = ControlPlaneSetting(
                plane=str(plane),
                enabled=bool(enabled),
                updated_at=float(updated_at),
                updated_by=str(updated_by),
            )
        return result

    def get(self, plane: str) -> ControlPlaneSetting | None:
        if plane not in PLANE_NAMES:
            return None
        if not self._db_path:
            return self._memory.get(plane)
        return self.get_all().get(plane)

    def set(
        self,
        plane: str,
        *,
        enabled: bool,
        updated_by: str,
    ) -> ControlPlaneSetting:
        """Persist a toggle.

        Raises ``ValueError`` for unknown plane names so a typo from
        the route handler turns into a clean 400 rather than silent
        corruption.
        """
        if plane not in PLANE_NAMES:
            raise ValueError(
                f"Unknown control plane: {plane!r}. "
                f"Expected one of: {sorted(PLANE_NAMES)}."
            )
        record = ControlPlaneSetting(
            plane=plane,
            enabled=bool(enabled),
            updated_at=time.time(),
            updated_by=str(updated_by) or "unknown",
        )

        if not self._db_path:
            self._memory[plane] = record
            return record

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO purecipher_registry_control_planes
                    (plane, enabled, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plane) DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (record.plane, int(record.enabled), record.updated_at, record.updated_by),
            )
            conn.commit()
        finally:
            conn.close()
        return record

    def known_planes(self) -> Iterable[str]:
        """Convenience: iterate canonical plane names."""
        return iter(sorted(PLANE_NAMES))


__all__ = [
    "PLANE_NAMES",
    "ControlPlaneSetting",
    "RegistryControlPlaneStore",
]

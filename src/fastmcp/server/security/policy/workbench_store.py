"""Persistent policy workbench state for UI-centric management flows.

This store keeps policy packs, captured environment baselines, promotion
records, and analytics history outside the core policy engine. The data is
JSON-safe and can be backed by either the in-memory or SQLite storage
backends.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from fastmcp.server.security.policy.serialization import describe_policy_config
from fastmcp.server.security.storage.backend import StorageBackend

_DEFAULT_STATE: dict[str, Any] = {
    "saved_packs": {},
    "environments": {},
    "promotions": [],
    "analytics_snapshots": [],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(snapshot)


class PolicyWorkbenchStore:
    """Persist higher-level policy workbench state for one policy set."""

    def __init__(
        self,
        policy_set_id: str,
        *,
        backend: StorageBackend | None = None,
    ) -> None:
        self.policy_set_id = policy_set_id
        self._backend = backend
        self._state: dict[str, Any] = copy.deepcopy(_DEFAULT_STATE)
        self._load()

    def _load(self) -> None:
        if self._backend is None:
            return
        data = self._backend.load_policy_workbench_state(self.policy_set_id)
        if data is None:
            return
        self._state = {
            "saved_packs": dict(data.get("saved_packs", {})),
            "environments": dict(data.get("environments", {})),
            "promotions": list(data.get("promotions", [])),
            "analytics_snapshots": list(data.get("analytics_snapshots", [])),
        }

    def _save(self) -> None:
        if self._backend is None:
            return
        self._backend.save_policy_workbench_state(
            self.policy_set_id,
            copy.deepcopy(self._state),
        )

    def list_saved_packs(self) -> list[dict[str, Any]]:
        """Return saved private packs, newest first."""
        packs = list(self._state["saved_packs"].values())
        packs.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return copy.deepcopy(packs)

    def get_saved_pack(self, pack_id: str) -> dict[str, Any] | None:
        """Return one saved pack by identifier."""
        pack = self._state["saved_packs"].get(pack_id)
        return copy.deepcopy(pack) if isinstance(pack, dict) else None

    def save_pack(
        self,
        *,
        title: str,
        summary: str,
        description: str,
        snapshot: dict[str, Any],
        author: str,
        tags: list[str] | None = None,
        recommended_environments: list[str] | None = None,
        pack_id: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Create or update a private reusable pack."""

        existing = (
            self._state["saved_packs"].get(pack_id)
            if pack_id is not None
            else None
        )
        current_id = pack_id or str(uuid.uuid4())
        created_at = (
            str(existing.get("created_at"))
            if isinstance(existing, dict)
            else _utc_now()
        )
        revisions = (
            list(existing.get("revisions", [])) if isinstance(existing, dict) else []
        )
        revision_number = len(revisions) + 1
        providers = snapshot.get("providers", [])
        provider_configs = [item for item in providers if isinstance(item, dict)]
        revision = {
            "revision_id": str(uuid.uuid4()),
            "revision_number": revision_number,
            "created_at": _utc_now(),
            "author": author,
            "note": note,
            "snapshot": _copy_snapshot(snapshot),
        }
        revisions.append(revision)
        pack = {
            "pack_id": current_id,
            "title": title.strip() or current_id,
            "summary": summary.strip(),
            "description": description.strip(),
            "owner": author,
            "visibility": "private",
            "tags": sorted({tag.strip() for tag in tags or [] if tag.strip()}),
            "recommended_environments": sorted(
                {
                    environment.strip()
                    for environment in recommended_environments or []
                    if environment.strip()
                }
            ),
            "provider_count": len(provider_configs),
            "provider_summaries": [
                describe_policy_config(config) for config in provider_configs
            ],
            "snapshot": _copy_snapshot(snapshot),
            "created_at": created_at,
            "updated_at": revision["created_at"],
            "revision_count": len(revisions),
            "current_revision_number": revision_number,
            "revisions": revisions,
        }
        self._state["saved_packs"][current_id] = pack
        self._save()
        return copy.deepcopy(pack)

    def delete_pack(self, pack_id: str) -> bool:
        """Delete a saved pack."""
        deleted = self._state["saved_packs"].pop(pack_id, None) is not None
        if deleted:
            self._save()
        return deleted

    def capture_environment(
        self,
        *,
        environment_id: str,
        snapshot: dict[str, Any],
        actor: str,
        source_label: str,
        version_number: int | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Capture a snapshot as the current baseline for one environment."""

        existing = self._state["environments"].get(environment_id, {})
        captures = list(existing.get("captures", []))
        providers = snapshot.get("providers", [])
        provider_count = len([item for item in providers if isinstance(item, dict)])
        capture = {
            "capture_id": str(uuid.uuid4()),
            "captured_at": _utc_now(),
            "captured_by": actor,
            "note": note,
            "source_label": source_label,
            "version_number": version_number,
            "provider_count": provider_count,
            "snapshot": _copy_snapshot(snapshot),
        }
        captures.append(capture)
        state = {
            "environment_id": environment_id,
            "current": capture,
            "capture_count": len(captures),
            "captures": captures[-12:],
        }
        self._state["environments"][environment_id] = state
        self._save()
        return copy.deepcopy(state)

    def get_environment_state(self, environment_id: str) -> dict[str, Any] | None:
        """Return one environment capture state."""
        state = self._state["environments"].get(environment_id)
        return copy.deepcopy(state) if isinstance(state, dict) else None

    def list_environment_states(self) -> list[dict[str, Any]]:
        """Return all captured environment states."""
        values = list(self._state["environments"].values())
        values.sort(key=lambda item: str(item.get("environment_id", "")))
        return copy.deepcopy(values)

    def record_promotion(
        self,
        *,
        source_environment: str,
        target_environment: str,
        actor: str,
        note: str,
        proposal_id: str,
        source_version_number: int | None,
        target_version_number: int | None,
    ) -> dict[str, Any]:
        """Record a staged promotion proposal."""

        record = {
            "promotion_id": str(uuid.uuid4()),
            "proposal_id": proposal_id,
            "source_environment": source_environment,
            "target_environment": target_environment,
            "source_version_number": source_version_number,
            "target_version_number": target_version_number,
            "status": "staged",
            "created_at": _utc_now(),
            "created_by": actor,
            "note": note,
            "decision_trail": [
                {
                    "event": "staged",
                    "actor": actor,
                    "note": note or "Promotion proposal created.",
                    "created_at": _utc_now(),
                }
            ],
        }
        promotions = self._state["promotions"]
        promotions.append(record)
        self._state["promotions"] = promotions[-50:]
        self._save()
        return copy.deepcopy(record)

    def update_promotion_from_proposal(
        self,
        *,
        proposal_id: str,
        status: str,
        actor: str,
        note: str = "",
        deployed_version_number: int | None = None,
    ) -> dict[str, Any] | None:
        """Update a promotion record based on a proposal lifecycle event."""

        promotions = self._state["promotions"]
        for promotion in promotions:
            if promotion.get("proposal_id") != proposal_id:
                continue
            promotion["status"] = status
            if deployed_version_number is not None:
                promotion["deployed_version_number"] = deployed_version_number
            if status in {"deployed", "rejected", "withdrawn"}:
                promotion["completed_at"] = _utc_now()
            promotion.setdefault("decision_trail", []).append(
                {
                    "event": status,
                    "actor": actor,
                    "note": note,
                    "created_at": _utc_now(),
                }
            )
            self._save()
            return copy.deepcopy(promotion)
        return None

    def list_promotions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent promotion records, newest first."""
        promotions = list(self._state["promotions"])
        promotions.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return copy.deepcopy(promotions[:limit])

    def record_analytics_snapshot(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Append a lightweight analytics point and return recent history."""

        history = list(self._state["analytics_snapshots"])
        last = history[-1] if history else None
        if not isinstance(last, dict) or any(
            last.get(key) != snapshot.get(key)
            for key in (
                "current_version",
                "provider_count",
                "evaluation_count",
                "deny_count",
                "deny_rate",
                "pending_proposals",
                "stale_proposals",
                "risk_count",
                "alert_count",
            )
        ):
            history.append(
                {
                    "captured_at": _utc_now(),
                    **snapshot,
                }
            )
            history = history[-60:]
            self._state["analytics_snapshots"] = history
            self._save()
        return copy.deepcopy(history[-20:])

    def list_analytics_history(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent analytics snapshots, newest last."""
        history = list(self._state["analytics_snapshots"])
        return copy.deepcopy(history[-limit:])

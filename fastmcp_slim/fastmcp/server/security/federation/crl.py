"""Certificate Revocation List (CRL) for SecureMCP.

Maintains a list of revoked tool attestations with reasons, timestamps,
and revocation propagation. Supports emergency revocation with
immediate blocking and event bus notification.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp.server.security.alerts.bus import SecurityEventBus

logger = logging.getLogger(__name__)


class RevocationReason(Enum):
    """Reasons for revoking a tool attestation."""

    KEY_COMPROMISE = "key_compromise"
    POLICY_VIOLATION = "policy_violation"
    SECURITY_INCIDENT = "security_incident"
    SUPERSEDED = "superseded"
    CESSATION_OF_OPERATION = "cessation_of_operation"
    PRIVILEGE_WITHDRAWN = "privilege_withdrawn"
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    MANUAL_REVOCATION = "manual_revocation"
    FEDERATION_PROPAGATION = "federation_propagation"


@dataclass
class CRLEntry:
    """An entry in the certificate revocation list.

    Attributes:
        entry_id: Unique entry identifier.
        tool_name: Name of the revoked tool.
        attestation_id: ID of the revoked attestation.
        reason: Why the attestation was revoked.
        revoked_at: When the revocation occurred.
        revoked_by: Who initiated the revocation.
        propagated: Whether this was propagated from a peer.
        source_peer_id: Peer that originated the revocation (if propagated).
        emergency: Whether this is an emergency revocation.
        description: Additional context.
        metadata: Extra data.
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    tool_name: str = ""
    attestation_id: str = ""
    reason: RevocationReason = RevocationReason.MANUAL_REVOCATION
    revoked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_by: str = ""
    propagated: bool = False
    source_peer_id: str = ""
    emergency: bool = False
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entry_id": self.entry_id,
            "tool_name": self.tool_name,
            "attestation_id": self.attestation_id,
            "reason": self.reason.value,
            "revoked_at": self.revoked_at.isoformat(),
            "revoked_by": self.revoked_by,
            "propagated": self.propagated,
            "source_peer_id": self.source_peer_id,
            "emergency": self.emergency,
            "description": self.description,
        }


class CertificateRevocationList:
    """Certificate Revocation List for managing revoked attestations.

    Tracks revoked tool attestations and provides fast lookups.
    Integrates with the SecurityEventBus for revocation alerts.

    Example::

        crl = CertificateRevocationList()

        # Revoke a tool
        entry = crl.revoke(
            tool_name="malicious-tool",
            attestation_id="att-123",
            reason=RevocationReason.SECURITY_INCIDENT,
            revoked_by="admin",
            emergency=True,
        )

        # Check if a tool is revoked
        assert crl.is_revoked("malicious-tool")

        # Get revocation details
        entries = crl.get_entries("malicious-tool")
    """

    def __init__(
        self,
        *,
        crl_id: str = "default",
        event_bus: SecurityEventBus | None = None,
    ) -> None:
        self._crl_id = crl_id
        self._event_bus = event_bus
        self._entries: dict[str, CRLEntry] = {}  # entry_id → CRLEntry
        self._tool_index: dict[str, list[str]] = {}  # tool_name → [entry_ids]
        self._attestation_index: dict[str, str] = {}  # attestation_id → entry_id

    @property
    def crl_id(self) -> str:
        """CRL instance identifier."""
        return self._crl_id

    def revoke(
        self,
        tool_name: str,
        *,
        attestation_id: str = "",
        reason: RevocationReason = RevocationReason.MANUAL_REVOCATION,
        revoked_by: str = "",
        emergency: bool = False,
        description: str = "",
        propagated: bool = False,
        source_peer_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CRLEntry:
        """Revoke a tool attestation.

        Args:
            tool_name: Name of the tool to revoke.
            attestation_id: Specific attestation to revoke.
            reason: Revocation reason.
            revoked_by: Who initiated the revocation.
            emergency: Whether this is an emergency revocation.
            description: Additional context.
            propagated: Whether this came from a federation peer.
            source_peer_id: Originating peer ID.
            metadata: Extra data.

        Returns:
            The created CRL entry.
        """
        entry = CRLEntry(
            tool_name=tool_name,
            attestation_id=attestation_id,
            reason=reason,
            revoked_by=revoked_by,
            emergency=emergency,
            description=description,
            propagated=propagated,
            source_peer_id=source_peer_id,
            metadata=metadata or {},
        )

        self._entries[entry.entry_id] = entry

        if tool_name not in self._tool_index:
            self._tool_index[tool_name] = []
        self._tool_index[tool_name].append(entry.entry_id)

        if attestation_id:
            self._attestation_index[attestation_id] = entry.entry_id

        self._emit_revocation_event(entry)

        logger.warning(
            "Tool revoked: %s (reason: %s, emergency: %s)",
            tool_name,
            reason.value,
            emergency,
        )

        return entry

    def is_revoked(self, tool_name: str) -> bool:
        """Check if a tool has any active revocations."""
        return tool_name in self._tool_index and len(self._tool_index[tool_name]) > 0

    def is_attestation_revoked(self, attestation_id: str) -> bool:
        """Check if a specific attestation has been revoked."""
        return attestation_id in self._attestation_index

    def get_entries(self, tool_name: str) -> list[CRLEntry]:
        """Get all revocation entries for a tool."""
        entry_ids = self._tool_index.get(tool_name, [])
        return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def get_entry(self, entry_id: str) -> CRLEntry | None:
        """Get a specific CRL entry."""
        return self._entries.get(entry_id)

    def get_entry_by_attestation(self, attestation_id: str) -> CRLEntry | None:
        """Get the CRL entry for a specific attestation."""
        entry_id = self._attestation_index.get(attestation_id)
        if entry_id is None:
            return None
        return self._entries.get(entry_id)

    def unrevoke(self, tool_name: str) -> int:
        """Remove all revocation entries for a tool.

        Returns the number of entries removed.
        """
        entry_ids = self._tool_index.pop(tool_name, [])
        count = 0
        for eid in entry_ids:
            entry = self._entries.pop(eid, None)
            if entry is not None:
                count += 1
                if entry.attestation_id:
                    self._attestation_index.pop(entry.attestation_id, None)
        return count

    def get_all_entries(self) -> list[CRLEntry]:
        """Get all CRL entries."""
        return list(self._entries.values())

    def get_emergency_entries(self) -> list[CRLEntry]:
        """Get only emergency revocation entries."""
        return [e for e in self._entries.values() if e.emergency]

    def get_propagated_entries(self) -> list[CRLEntry]:
        """Get entries that were propagated from peers."""
        return [e for e in self._entries.values() if e.propagated]

    @property
    def entry_count(self) -> int:
        """Total number of CRL entries."""
        return len(self._entries)

    @property
    def revoked_tool_count(self) -> int:
        """Number of distinct tools with revocations."""
        return len(self._tool_index)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire CRL."""
        return {
            "crl_id": self._crl_id,
            "entry_count": self.entry_count,
            "revoked_tools": self.revoked_tool_count,
            "entries": [e.to_dict() for e in self._entries.values()],
        }

    def _emit_revocation_event(self, entry: CRLEntry) -> None:
        """Emit a security event for a revocation."""
        if self._event_bus is None:
            return

        from fastmcp.server.security.alerts.models import (
            AlertSeverity,
            SecurityEvent,
            SecurityEventType,
        )

        severity = AlertSeverity.CRITICAL if entry.emergency else AlertSeverity.WARNING

        self._event_bus.emit(
            SecurityEvent(
                event_type=SecurityEventType.TRUST_CHANGED,
                severity=severity,
                layer="federation",
                message=f"Tool revoked: {entry.tool_name} — {entry.reason.value}",
                resource_id=entry.tool_name,
                data=entry.to_dict(),
            )
        )

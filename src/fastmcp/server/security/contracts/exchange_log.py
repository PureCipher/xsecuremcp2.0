"""Non-repudiation exchange log for contract negotiations.

Records all negotiation events with cryptographic hashes for tamper detection.
This forms the audit trail that feeds into the Phase 3 Provenance Ledger.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastmcp.server.security.storage.backend import StorageBackend

logger = logging.getLogger(__name__)

# Legacy logs wrote the literal string ``"genesis"`` as the first
# entry's ``previous_hash`` per session. New chains use a per-session
# random nonce to prevent forgery of fresh chains rooted at a guessable
# sentinel. Both forms are accepted by ``verify_chain`` for back-compat.
_LEGACY_EXCHANGE_GENESIS_SENTINEL = "genesis"


class ExchangeEventType(Enum):
    """Types of exchange events recorded in the log."""

    SESSION_STARTED = "session_started"
    PROPOSAL_SENT = "proposal_sent"
    PROPOSAL_RECEIVED = "proposal_received"
    COUNTER_SENT = "counter_sent"
    COUNTER_RECEIVED = "counter_received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONTRACT_SIGNED = "contract_signed"
    CONTRACT_EXPIRED = "contract_expired"
    CONTRACT_REVOKED = "contract_revoked"
    AGENT_SIGNED = "agent_signed"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"


@dataclass(frozen=True)
class ExchangeLogEntry:
    """A single entry in the exchange log.

    Each entry is hash-linked to the previous entry in the same
    session, forming a tamper-evident chain.

    Attributes:
        entry_id: Unique entry identifier.
        session_id: The negotiation session.
        event_type: What happened.
        timestamp: When the event occurred.
        actor_id: Who triggered the event.
        data: Event-specific payload.
        data_hash: SHA-256 hash of the data payload.
        previous_hash: Hash of the previous entry in this session's chain.
    """

    entry_id: str
    session_id: str
    event_type: ExchangeEventType
    timestamp: datetime
    actor_id: str
    data: dict[str, Any] = field(default_factory=dict)
    data_hash: str = ""
    previous_hash: str = ""

    def compute_hash(self) -> str:
        """Compute the hash of this entry for chain linking."""
        payload = {
            "entry_id": self.entry_id,
            "session_id": self.session_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "data_hash": self.data_hash,
            "previous_hash": self.previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ExchangeLog:
    """Append-only exchange log with hash-chain integrity.

    Records all negotiation events for non-repudiation. Each session
    maintains its own hash chain for independent verification.

    Example::

        log = ExchangeLog()
        entry = log.record(
            session_id="sess-1",
            event_type=ExchangeEventType.SESSION_STARTED,
            actor_id="server-1",
            data={"agent_id": "agent-abc"},
        )
        assert log.verify_chain("sess-1")
    """

    def __init__(
        self,
        log_id: str = "default",
        *,
        backend: StorageBackend | None = None,
    ) -> None:
        self.log_id = log_id
        self._backend = backend
        self._entries: list[ExchangeLogEntry] = []
        self._session_chains: dict[str, list[ExchangeLogEntry]] = {}
        # Per-session genesis nonce. Mixed with random entropy so an
        # attacker can't forge a fresh chain rooted at a known sentinel.
        # On reload from backend, recovered from the first entry's
        # ``previous_hash`` (which may be the legacy literal ``"genesis"``
        # for older logs).
        self._session_genesis: dict[str, str] = {}
        self._entry_counter = 0

        # Load persisted entries and rebuild session chains
        if self._backend is not None:
            self._load_from_backend()

    def _get_or_create_session_genesis(self, session_id: str) -> str:
        """Return this session's genesis nonce, generating one on first use."""
        existing = self._session_genesis.get(session_id)
        if existing is not None:
            return existing
        nonce = (
            f"genesis-{self.log_id}-{session_id}-{secrets.token_hex(32)}"
        )
        self._session_genesis[session_id] = nonce
        return nonce

    def get_session_genesis(self, session_id: str) -> str | None:
        """Return the per-session genesis nonce (or ``None`` if unused)."""
        return self._session_genesis.get(session_id)

    def _load_from_backend(self) -> None:
        """Load entries from backend and rebuild session chains."""
        if self._backend is None:
            return
        from fastmcp.server.security.storage.serialization import (
            exchange_entry_from_dict,
        )

        raw_entries = self._backend.load_exchange_entries(self.log_id)
        for data in raw_entries:
            entry = exchange_entry_from_dict(data)
            self._entries.append(entry)
            self._entry_counter += 1
            sid = entry.session_id
            if sid not in self._session_chains:
                self._session_chains[sid] = []
                # Recover this session's genesis nonce from the first
                # persisted entry so verify_chain matches what was written.
                self._session_genesis[sid] = entry.previous_hash
            self._session_chains[sid].append(entry)

    def record(
        self,
        session_id: str,
        event_type: ExchangeEventType,
        actor_id: str,
        data: dict[str, Any] | None = None,
    ) -> ExchangeLogEntry:
        """Record an event in the exchange log.

        Args:
            session_id: The negotiation session.
            event_type: What happened.
            actor_id: Who triggered the event.
            data: Event-specific payload.

        Returns:
            The recorded log entry with computed hashes.
        """
        data = data or {}
        self._entry_counter += 1

        # Compute data hash
        data_canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        data_hash = hashlib.sha256(data_canonical.encode("utf-8")).hexdigest()

        # Get previous hash in this session's chain (or this session's
        # randomized genesis nonce for the very first entry).
        session_chain = self._session_chains.get(session_id, [])
        previous_hash = (
            session_chain[-1].compute_hash()
            if session_chain
            else self._get_or_create_session_genesis(session_id)
        )

        entry = ExchangeLogEntry(
            entry_id=f"exlog-{self._entry_counter:06d}",
            session_id=session_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_id=actor_id,
            data=data,
            data_hash=data_hash,
            previous_hash=previous_hash,
        )

        self._entries.append(entry)
        if session_id not in self._session_chains:
            self._session_chains[session_id] = []
        self._session_chains[session_id].append(entry)

        # Persist to backend
        if self._backend is not None:
            from fastmcp.server.security.storage.serialization import (
                exchange_entry_to_dict,
            )

            self._backend.append_exchange_entry(
                self.log_id, exchange_entry_to_dict(entry)
            )

        logger.debug(
            "ExchangeLog: recorded %s for session %s by %s",
            event_type.value,
            session_id,
            actor_id,
        )

        return entry

    def get_session_entries(self, session_id: str) -> list[ExchangeLogEntry]:
        """Get all entries for a specific session."""
        return list(self._session_chains.get(session_id, []))

    def get_all_entries(self) -> list[ExchangeLogEntry]:
        """Get all entries across all sessions."""
        return list(self._entries)

    def verify_chain(self, session_id: str) -> bool:
        """Verify the hash chain integrity for a session.

        Returns True if the chain is intact, False if tampered.
        """
        chain = self._session_chains.get(session_id, [])
        if not chain:
            return True  # Empty chain is valid

        # Verify first entry links to this session's genesis nonce, or
        # to the legacy ``"genesis"`` literal for chains persisted before
        # the per-session nonce was introduced.
        first_link = chain[0].previous_hash
        expected_genesis = self._session_genesis.get(session_id)
        if expected_genesis is None or first_link != expected_genesis:
            if first_link != _LEGACY_EXCHANGE_GENESIS_SENTINEL:
                logger.warning(
                    "Chain for session %s: invalid genesis link", session_id
                )
                return False

        # Verify each subsequent entry links to the previous
        for i in range(1, len(chain)):
            expected_prev = chain[i - 1].compute_hash()
            if chain[i].previous_hash != expected_prev:
                logger.warning(
                    "Chain for session %s: broken at entry %d",
                    session_id,
                    i,
                )
                return False

        return True

    @staticmethod
    def entry_to_dict(entry: ExchangeLogEntry) -> dict[str, Any]:
        """Serialize a single entry to a dictionary for export or API responses."""
        return {
            "entry_id": entry.entry_id,
            "session_id": entry.session_id,
            "event_type": entry.event_type.value,
            "timestamp": entry.timestamp.isoformat(),
            "actor_id": entry.actor_id,
            "data": entry.data,
            "data_hash": entry.data_hash,
            "previous_hash": entry.previous_hash,
        }

    def export_entries(
        self,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export entries as serializable dictionaries.

        Args:
            session_id: If provided, return only entries for this session.
                Otherwise, return all entries.

        Returns:
            List of entry dictionaries.
        """
        if session_id is not None:
            entries = self.get_session_entries(session_id)
        else:
            entries = self.get_all_entries()
        return [self.entry_to_dict(e) for e in entries]

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Get an audit summary for a negotiation session.

        Returns:
            Dictionary with entry count, event list, verification stats,
            and chain integrity status.
        """
        chain = self._session_chains.get(session_id, [])
        if not chain:
            return {
                "session_id": session_id,
                "entry_count": 0,
                "events": [],
                "verification_passed": 0,
                "verification_failed": 0,
                "chain_verified": True,
            }

        events = [e.event_type.value for e in chain]
        verification_passed = sum(
            1 for e in chain if e.event_type == ExchangeEventType.VERIFICATION_PASSED
        )
        verification_failed = sum(
            1 for e in chain if e.event_type == ExchangeEventType.VERIFICATION_FAILED
        )

        return {
            "session_id": session_id,
            "entry_count": len(chain),
            "started_at": chain[0].timestamp.isoformat(),
            "ended_at": chain[-1].timestamp.isoformat(),
            "events": events,
            "verification_passed": verification_passed,
            "verification_failed": verification_failed,
            "chain_verified": self.verify_chain(session_id),
        }

    @property
    def entry_count(self) -> int:
        """Total number of entries across all sessions."""
        return len(self._entries)

    @property
    def session_count(self) -> int:
        """Number of distinct sessions."""
        return len(self._session_chains)

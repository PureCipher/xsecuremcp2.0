"""Provenance Ledger for SecureMCP.

Central audit trail that records all MCP operations with hash-chain
integrity and Merkle tree verification. Provides efficient queries
and tamper detection for the full operation history.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastmcp.server.security.provenance.merkle import MerkleTree
from fastmcp.server.security.provenance.records import (
    ProvenanceAction,
    ProvenanceRecord,
    hash_data,
)
from fastmcp.server.security.storage.backend import StorageBackend

if TYPE_CHECKING:
    from fastmcp.server.security.alerts.bus import SecurityEventBus
    from fastmcp.server.security.provenance.schemes import LedgerScheme

logger = logging.getLogger(__name__)

# Legacy ledgers wrote the literal string ``"genesis"`` as the first
# record's ``previous_hash``. New ledgers use a per-instance random
# nonce so an attacker who knows the format can't forge a fresh chain
# rooted at a guessable sentinel. Both forms are accepted by
# ``verify_chain`` for backward compatibility.
_LEGACY_GENESIS_SENTINEL = "genesis"


class ProvenanceLedger:
    """Append-only provenance ledger with hash-chain and Merkle tree integrity.

    Every operation recorded gets:
    1. A hash-chained link to the previous record (sequential integrity)
    2. A Merkle tree leaf for efficient batch verification

    Supports pluggable ledger schemes via the ``scheme`` parameter:

    - ``LocalMerkleLedger`` (default): Fast in-process Merkle tree.
    - ``BlockchainAnchoredLedger``: Local Merkle + periodic external
      chain anchoring for distributed trust.

    Example::

        ledger = ProvenanceLedger()

        record = ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent-1",
            resource_id="calculator",
            input_data={"expression": "2+2"},
        )

        # Verify chain integrity
        assert ledger.verify_chain()

        # Verify Merkle tree
        assert ledger.verify_tree()

        # Get proof for a specific record
        proof = ledger.get_proof(record.record_id)
        assert proof.verify()

    Args:
        ledger_id: Unique identifier for this ledger instance.
        scheme: Optional pluggable ledger scheme. If None, uses
            an internal MerkleTree directly (equivalent to LocalMerkleLedger).
    """

    def __init__(
        self,
        ledger_id: str = "default",
        *,
        backend: StorageBackend | None = None,
        event_bus: SecurityEventBus | None = None,
        scheme: LedgerScheme | None = None,
        genesis_hash: str | None = None,
    ) -> None:
        self.ledger_id = ledger_id
        self._backend = backend
        self._event_bus = event_bus
        self._scheme = scheme
        self._records: list[ProvenanceRecord] = []
        self._record_index: dict[str, int] = {}
        self._merkle_tree = MerkleTree()
        # Per-ledger genesis nonce. Mixed with random entropy so an
        # attacker can't forge a fresh chain rooted at a guessable
        # sentinel. Materialized lazily on the first ``record()`` call
        # if not provided by the caller, then frozen for the ledger's
        # lifetime. When loading from a backend we recover whatever
        # nonce the first persisted record used (which may be the
        # ``_LEGACY_GENESIS_SENTINEL`` for old ledgers).
        self._genesis_hash: str | None = genesis_hash

        # Load persisted records and rebuild indices
        if self._backend is not None:
            self._load_from_backend()

    def _load_from_backend(self) -> None:
        """Load records from backend and rebuild index + Merkle tree."""
        if self._backend is None:
            return
        from fastmcp.server.security.storage.serialization import (
            provenance_record_from_dict,
        )

        raw_records = self._backend.load_provenance_records(self.ledger_id)
        for i, data in enumerate(raw_records):
            rec = provenance_record_from_dict(data)
            self._records.append(rec)
            self._record_index[rec.record_id] = i
            record_hash = rec.compute_hash()
            self._merkle_tree.add_leaf(record_hash)
            if self._scheme is not None:
                self._scheme.add_record_hash(record_hash)
        # Recover the genesis hash from the first persisted record so
        # subsequent verify_chain calls match what was written.
        if self._records and self._genesis_hash is None:
            self._genesis_hash = self._records[0].previous_hash

    def _get_or_create_genesis_hash(self) -> str:
        """Return the per-ledger genesis nonce, generating one on first use."""
        if self._genesis_hash is None:
            # 32 random bytes = 64 hex chars. Mixed with the ledger_id
            # so it's visually distinguishable from a record hash and so
            # different ledgers can't accidentally share a root.
            self._genesis_hash = (
                f"genesis-{self.ledger_id}-{secrets.token_hex(32)}"
            )
        return self._genesis_hash

    @property
    def genesis_hash(self) -> str | None:
        """The ledger's genesis nonce (or ``None`` if no records yet exist)."""
        return self._genesis_hash

    def attach_event_bus(self, event_bus: SecurityEventBus | None) -> None:
        """Wire an event bus into this ledger after construction.

        Public alternative to assigning to the private ``_event_bus``
        attribute. Used by the security orchestrator and by application
        code that builds the ledger before the bus exists.
        """
        self._event_bus = event_bus

    def record(
        self,
        action: ProvenanceAction,
        actor_id: str,
        resource_id: str = "",
        *,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict[str, Any] | None = None,
        contract_id: str = "",
        session_id: str = "",
    ) -> ProvenanceRecord:
        """Record a provenance event.

        Args:
            action: Type of action being recorded.
            actor_id: Who performed the action.
            resource_id: What was acted upon.
            input_data: Input/request data (will be hashed).
            output_data: Output/response data (will be hashed).
            metadata: Additional context.
            contract_id: Associated contract.
            session_id: Session context.

        Returns:
            The recorded ProvenanceRecord with computed hashes.
        """
        # Compute content hashes
        input_hash = hash_data(input_data) if input_data is not None else ""
        output_hash = hash_data(output_data) if output_data is not None else ""

        # Chain to previous record (or to the per-ledger genesis nonce
        # for the very first record).
        previous_hash = (
            self._records[-1].compute_hash()
            if self._records
            else self._get_or_create_genesis_hash()
        )

        entry = ProvenanceRecord(
            action=action,
            actor_id=actor_id,
            resource_id=resource_id,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=metadata or {},
            previous_hash=previous_hash,
            contract_id=contract_id,
            session_id=session_id,
        )

        # Store and index
        idx = len(self._records)
        self._records.append(entry)
        self._record_index[entry.record_id] = idx

        # Add to Merkle tree (and scheme if configured)
        record_hash = entry.compute_hash()
        self._merkle_tree.add_leaf(record_hash)
        if self._scheme is not None:
            self._scheme.add_record_hash(record_hash)

        # Persist to backend
        if self._backend is not None:
            from fastmcp.server.security.storage.serialization import (
                provenance_record_to_dict,
            )

            self._backend.append_provenance_record(
                self.ledger_id, provenance_record_to_dict(entry)
            )

        # Emit alert event
        if self._event_bus is not None:
            from fastmcp.server.security.alerts.models import (
                AlertSeverity,
                SecurityEvent,
                SecurityEventType,
            )

            self._event_bus.emit(
                SecurityEvent(
                    event_type=SecurityEventType.PROVENANCE_RECORDED,
                    severity=AlertSeverity.INFO,
                    layer="provenance",
                    message=f"Provenance: {action.value} by {actor_id}",
                    actor_id=actor_id,
                    resource_id=resource_id,
                    data={
                        "action": action.value,
                        "record_id": entry.record_id,
                    },
                )
            )

        logger.debug(
            "Provenance: recorded %s by %s on %s (record %s)",
            action.value,
            actor_id,
            resource_id,
            entry.record_id[:8],
        )

        return entry

    def get_record(self, record_id: str) -> ProvenanceRecord | None:
        """Look up a record by ID."""
        idx = self._record_index.get(record_id)
        if idx is None:
            return None
        return self._records[idx]

    def get_records(
        self,
        *,
        action: ProvenanceAction | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[ProvenanceRecord]:
        """Query records with optional filters.

        Args:
            action: Filter by action type.
            actor_id: Filter by actor.
            resource_id: Filter by resource.
            since: Only records after this timestamp.
            until: Only records before this timestamp.
            limit: Maximum number of records to return.

        Returns:
            List of matching records, most recent first.
        """
        results: list[ProvenanceRecord] = []

        for rec in reversed(self._records):
            if action is not None and rec.action != action:
                continue
            if actor_id is not None and rec.actor_id != actor_id:
                continue
            if resource_id is not None and rec.resource_id != resource_id:
                continue
            if since is not None and rec.timestamp < since:
                continue
            if until is not None and rec.timestamp > until:
                continue
            results.append(rec)
            if len(results) >= limit:
                break

        return results

    def verify_chain(self) -> bool:
        """Verify the hash chain integrity of all records.

        Returns True if the chain is intact, False if tampered.
        """
        if not self._records:
            return True

        # First record must link to either this ledger's genesis nonce
        # (current behaviour) or the literal legacy ``"genesis"`` string
        # (back-compat for ledgers persisted before the nonce was added).
        first_link = self._records[0].previous_hash
        expected_genesis = self._genesis_hash
        if expected_genesis is None or first_link != expected_genesis:
            if first_link != _LEGACY_GENESIS_SENTINEL:
                logger.warning("Provenance chain: invalid genesis link")
                return False

        # Each subsequent record should link to the hash of its predecessor
        for i in range(1, len(self._records)):
            expected = self._records[i - 1].compute_hash()
            if self._records[i].previous_hash != expected:
                logger.warning("Provenance chain: broken at record %d", i)
                return False

        return True

    def verify_tree(self) -> bool:
        """Verify the Merkle tree integrity."""
        return self._merkle_tree.verify_tree()

    def get_proof(self, record_id: str) -> Any:
        """Get a Merkle inclusion proof for a record.

        Args:
            record_id: The record to prove.

        Returns:
            MerkleProof for the record.

        Raises:
            KeyError: If record_id not found.
        """
        idx = self._record_index.get(record_id)
        if idx is None:
            raise KeyError(f"Record '{record_id}' not found in ledger")
        return self._merkle_tree.get_proof(idx)

    @property
    def root_hash(self) -> str:
        """Current Merkle root hash summarizing all records."""
        return self._merkle_tree.root_hash

    @property
    def record_count(self) -> int:
        """Total number of records in the ledger."""
        return len(self._records)

    @property
    def latest_record(self) -> ProvenanceRecord | None:
        """The most recently recorded entry."""
        return self._records[-1] if self._records else None

    def get_chain_digest(self) -> str:
        """Get a summary digest of the entire chain.

        Returns the hash of the last record, which transitively
        depends on all previous records.
        """
        if not self._records:
            return "empty"
        return self._records[-1].compute_hash()

    @property
    def scheme(self) -> LedgerScheme | None:
        """The pluggable ledger scheme, if configured."""
        return self._scheme

    @property
    def all_records(self) -> list[ProvenanceRecord]:
        """All records in insertion order (read-only copy)."""
        return list(self._records)

    def get_scheme_status(self) -> dict[str, Any]:
        """Get the ledger scheme status.

        Returns scheme-specific information (anchor status, tree stats, etc.)
        or basic Merkle tree info if no scheme is configured.
        """
        if self._scheme is not None:
            return self._scheme.get_status()
        return {
            "scheme": "internal_merkle",
            "leaf_count": self._merkle_tree.leaf_count,
            "root_hash": self.root_hash,
            "tree_valid": self.verify_tree(),
        }

    def export_verification_bundle(self, record_id: str) -> dict[str, Any]:
        """Export a self-contained verification bundle for a record.

        The bundle contains everything needed for an external auditor
        to independently verify the record's integrity and chain position.

        Args:
            record_id: The record to export a bundle for.

        Returns:
            A JSON-safe dict that can be verified with ``verify_bundle()``.

        Raises:
            KeyError: If the record is not found.
        """
        from fastmcp.server.security.provenance.export import VerificationBundle

        idx = self._record_index.get(record_id)
        if idx is None:
            raise KeyError(f"Record '{record_id}' not found in ledger")

        record = self._records[idx]
        proof = self._merkle_tree.get_proof(idx)

        # Chain context — use the actual previous_hash on the genesis
        # record (which may be the per-ledger nonce or, for legacy
        # ledgers, the literal ``"genesis"`` string).
        predecessor_hash = (
            self._records[0].previous_hash
            if idx == 0
            else self._records[idx - 1].compute_hash()
        )
        successor_hash = (
            self._records[idx + 1].compute_hash()
            if idx + 1 < len(self._records)
            else ""
        )

        bundle = VerificationBundle(
            record=record.to_dict(),
            proof_leaf_hash=proof.leaf_hash,
            proof_hashes=proof.proof_hashes,
            proof_directions=proof.directions,
            proof_root_hash=proof.root_hash,
            chain_predecessor_hash=predecessor_hash,
            chain_successor_hash=successor_hash,
            ledger_root_hash=self.root_hash,
            ledger_record_count=self.record_count,
        )

        return bundle.to_dict()

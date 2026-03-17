"""Pluggable ledger scheme abstraction for Smart Provenance.

Defines the ``LedgerScheme`` protocol that separates *how* integrity
evidence is managed from the core append-only ledger logic. Two
built-in implementations:

- ``LocalMerkleLedger``: In-process Merkle tree (default, zero latency).
- ``BlockchainAnchoredLedger``: Wraps a local Merkle tree and
  periodically commits the root hash to an external chain via a
  pluggable ``AnchorBackend``.

The ``ProvenanceLedger`` can be parameterized with any scheme that
satisfies the protocol.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from fastmcp.server.security.provenance.merkle import MerkleProof, MerkleTree

logger = logging.getLogger(__name__)


# ── Ledger Scheme Protocol ───────────────────────────────────────


class LedgerSchemeType(Enum):
    """Supported ledger scheme types."""

    LOCAL_MERKLE = "local_merkle"
    BLOCKCHAIN_ANCHORED = "blockchain_anchored"


@runtime_checkable
class LedgerScheme(Protocol):
    """Protocol for ledger integrity schemes.

    Implementations provide the cryptographic evidence layer —
    maintaining integrity data structures, generating proofs,
    and verifying the ledger state.
    """

    @property
    def scheme_type(self) -> LedgerSchemeType:
        """Return the type of this ledger scheme."""
        ...

    def add_record_hash(self, record_hash: str) -> int:
        """Register a record hash and return its index."""
        ...

    @property
    def root_hash(self) -> str:
        """Current root hash summarizing all records."""
        ...

    def verify(self) -> bool:
        """Verify the full integrity of the scheme's data structure."""
        ...

    def get_proof(self, index: int) -> MerkleProof:
        """Generate an inclusion proof for a record by index."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Return scheme-specific status information."""
        ...


# ── Local Merkle (default) ───────────────────────────────────────


class LocalMerkleLedger:
    """In-process Merkle tree integrity scheme.

    The simplest and fastest scheme — all integrity data lives in
    memory alongside the ledger. Suitable for single-node deployments
    where trust is established at the process level.

    Example::

        scheme = LocalMerkleLedger()
        idx = scheme.add_record_hash("abc123")
        assert scheme.verify()
        proof = scheme.get_proof(idx)
        assert proof.verify()
    """

    def __init__(self) -> None:
        self._tree = MerkleTree()

    @property
    def scheme_type(self) -> LedgerSchemeType:
        return LedgerSchemeType.LOCAL_MERKLE

    def add_record_hash(self, record_hash: str) -> int:
        return self._tree.add_leaf(record_hash)

    @property
    def root_hash(self) -> str:
        return self._tree.root_hash

    def verify(self) -> bool:
        return self._tree.verify_tree()

    def get_proof(self, index: int) -> MerkleProof:
        return self._tree.get_proof(index)

    def get_status(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme_type.value,
            "leaf_count": self._tree.leaf_count,
            "root_hash": self.root_hash,
            "tree_valid": self.verify(),
        }


# ── Anchor Backend Protocol ──────────────────────────────────────


@runtime_checkable
class AnchorBackend(Protocol):
    """Protocol for external chain anchoring.

    Implementations commit a Merkle root hash to an external
    immutable store (blockchain, timestamping service, etc.)
    and later verify that the commitment exists.
    """

    def commit(self, anchor: ChainAnchor) -> str:
        """Commit an anchor to the external chain.

        Returns:
            A transaction/reference ID from the external chain.
        """
        ...

    def verify_anchor(self, anchor: ChainAnchor) -> bool:
        """Verify that an anchor exists on the external chain."""
        ...

    def get_latest_anchor(self) -> ChainAnchor | None:
        """Retrieve the most recent anchor, if any."""
        ...


# ── Chain Anchor Record ──────────────────────────────────────────


@dataclass(frozen=True)
class ChainAnchor:
    """A commitment of a Merkle root hash to an external chain.

    Attributes:
        anchor_id: Unique identifier for this anchor.
        merkle_root: The Merkle root hash being committed.
        record_count: Number of records covered by this anchor.
        timestamp: When the anchor was created (UTC).
        chain_name: Name/identifier of the external chain.
        tx_id: Transaction/reference ID on the external chain.
        previous_anchor_id: The prior anchor for chain continuity.
        metadata: Additional anchor-specific context.
    """

    anchor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    merkle_root: str = ""
    record_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chain_name: str = ""
    tx_id: str = ""
    previous_anchor_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Compute SHA-256 of this anchor for chaining."""
        payload = {
            "anchor_id": self.anchor_id,
            "merkle_root": self.merkle_root,
            "record_count": self.record_count,
            "timestamp": self.timestamp.isoformat(),
            "chain_name": self.chain_name,
            "tx_id": self.tx_id,
            "previous_anchor_id": self.previous_anchor_id,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage and transport."""
        return {
            "anchor_id": self.anchor_id,
            "merkle_root": self.merkle_root,
            "record_count": self.record_count,
            "timestamp": self.timestamp.isoformat(),
            "chain_name": self.chain_name,
            "tx_id": self.tx_id,
            "previous_anchor_id": self.previous_anchor_id,
            "metadata": self.metadata,
        }


# ── In-Memory Anchor Backend (for testing / local trust) ─────────


class InMemoryAnchorBackend:
    """In-memory anchor backend for testing and local deployments.

    Stores anchors in a list. Useful for development and for
    environments where an external blockchain is not available
    but you still want the anchoring abstraction.

    Example::

        backend = InMemoryAnchorBackend(chain_name="local-test")
        anchor = ChainAnchor(merkle_root="abc123", record_count=10)
        tx_id = backend.commit(anchor)
        assert backend.verify_anchor(anchor)
    """

    def __init__(self, chain_name: str = "in-memory") -> None:
        self.chain_name = chain_name
        self._anchors: list[ChainAnchor] = []
        self._anchor_index: dict[str, ChainAnchor] = {}

    def commit(self, anchor: ChainAnchor) -> str:
        """Store anchor and return a synthetic tx_id."""
        tx_id = f"{self.chain_name}:tx:{len(self._anchors):06d}"
        # Create a new anchor with the tx_id filled in
        committed = ChainAnchor(
            anchor_id=anchor.anchor_id,
            merkle_root=anchor.merkle_root,
            record_count=anchor.record_count,
            timestamp=anchor.timestamp,
            chain_name=self.chain_name,
            tx_id=tx_id,
            previous_anchor_id=anchor.previous_anchor_id,
            metadata=anchor.metadata,
        )
        self._anchors.append(committed)
        self._anchor_index[committed.anchor_id] = committed
        return tx_id

    def verify_anchor(self, anchor: ChainAnchor) -> bool:
        """Check that an anchor with matching root exists."""
        stored = self._anchor_index.get(anchor.anchor_id)
        if stored is None:
            return False
        return stored.merkle_root == anchor.merkle_root

    def get_latest_anchor(self) -> ChainAnchor | None:
        """Return the most recent anchor."""
        return self._anchors[-1] if self._anchors else None

    @property
    def anchor_count(self) -> int:
        """Number of anchors committed."""
        return len(self._anchors)

    def get_all_anchors(self) -> list[ChainAnchor]:
        """Return all committed anchors in order."""
        return list(self._anchors)


# ── Blockchain-Anchored Ledger Scheme ────────────────────────────


class BlockchainAnchoredLedger:
    """Merkle tree + periodic external chain anchoring.

    Wraps a local ``MerkleTree`` for real-time integrity and
    periodically commits the root hash to an external chain via
    an ``AnchorBackend``. This provides the "distributed (blockchain)"
    trust model while keeping local performance high.

    Anchoring happens automatically every ``anchor_interval`` records,
    or can be triggered manually with ``anchor_now()``.

    Example::

        backend = InMemoryAnchorBackend(chain_name="ethereum-sepolia")
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend,
            anchor_interval=100,
        )

        for i in range(150):
            scheme.add_record_hash(f"hash-{i}")

        # First anchor committed automatically at record 100
        assert len(scheme.anchors) == 1

        # Force anchor for remaining 50
        scheme.anchor_now()
        assert len(scheme.anchors) == 2

    Args:
        anchor_backend: Where to commit Merkle roots.
        anchor_interval: Commit every N records. 0 = manual only.
    """

    def __init__(
        self,
        anchor_backend: AnchorBackend,
        anchor_interval: int = 100,
    ) -> None:
        self._tree = MerkleTree()
        self._anchor_backend = anchor_backend
        self._anchor_interval = anchor_interval
        self._anchors: list[ChainAnchor] = []
        self._records_since_anchor = 0

    @property
    def scheme_type(self) -> LedgerSchemeType:
        return LedgerSchemeType.BLOCKCHAIN_ANCHORED

    def add_record_hash(self, record_hash: str) -> int:
        """Add a record hash and auto-anchor if interval is reached."""
        idx = self._tree.add_leaf(record_hash)
        self._records_since_anchor += 1

        if (
            self._anchor_interval > 0
            and self._records_since_anchor >= self._anchor_interval
        ):
            self.anchor_now()

        return idx

    @property
    def root_hash(self) -> str:
        return self._tree.root_hash

    def verify(self) -> bool:
        """Verify local Merkle tree integrity."""
        return self._tree.verify_tree()

    def get_proof(self, index: int) -> MerkleProof:
        return self._tree.get_proof(index)

    def anchor_now(self) -> ChainAnchor:
        """Force an immediate anchor commitment.

        Returns:
            The committed ChainAnchor.
        """
        previous_id = self._anchors[-1].anchor_id if self._anchors else ""

        anchor = ChainAnchor(
            merkle_root=self.root_hash,
            record_count=self._tree.leaf_count,
            previous_anchor_id=previous_id,
        )

        tx_id = self._anchor_backend.commit(anchor)

        # Re-create with tx_id filled in
        committed = ChainAnchor(
            anchor_id=anchor.anchor_id,
            merkle_root=anchor.merkle_root,
            record_count=anchor.record_count,
            timestamp=anchor.timestamp,
            chain_name=anchor.chain_name,
            tx_id=tx_id,
            previous_anchor_id=anchor.previous_anchor_id,
            metadata=anchor.metadata,
        )

        self._anchors.append(committed)
        self._records_since_anchor = 0

        logger.info(
            "Chain anchor committed: root=%s records=%d tx=%s",
            committed.merkle_root[:16],
            committed.record_count,
            tx_id,
        )

        return committed

    def verify_anchors(self) -> bool:
        """Verify all anchors against the external chain."""
        for anchor in self._anchors:
            if not self._anchor_backend.verify_anchor(anchor):
                logger.warning(
                    "Anchor verification failed: %s",
                    anchor.anchor_id,
                )
                return False
        return True

    @property
    def anchors(self) -> list[ChainAnchor]:
        """All committed anchors in order."""
        return list(self._anchors)

    @property
    def latest_anchor(self) -> ChainAnchor | None:
        """The most recent anchor."""
        return self._anchors[-1] if self._anchors else None

    def get_status(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme_type.value,
            "leaf_count": self._tree.leaf_count,
            "root_hash": self.root_hash,
            "tree_valid": self.verify(),
            "anchor_count": len(self._anchors),
            "anchors_valid": self.verify_anchors(),
            "records_since_anchor": self._records_since_anchor,
            "anchor_interval": self._anchor_interval,
            "latest_anchor": self._anchors[-1].to_dict() if self._anchors else None,
        }

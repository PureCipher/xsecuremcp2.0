"""Tests for pluggable ledger schemes (Smart Provenance)."""

from __future__ import annotations

import pytest

from fastmcp.server.security.provenance.records import ProvenanceAction, hash_data
from fastmcp.server.security.provenance.schemes import (
    BlockchainAnchoredLedger,
    ChainAnchor,
    InMemoryAnchorBackend,
    LedgerScheme,
    LedgerSchemeType,
    LocalMerkleLedger,
)


# ── LocalMerkleLedger ────────────────────────────────────────────


class TestLocalMerkleLedger:
    def test_scheme_type(self) -> None:
        scheme = LocalMerkleLedger()
        assert scheme.scheme_type == LedgerSchemeType.LOCAL_MERKLE

    def test_satisfies_protocol(self) -> None:
        assert isinstance(LocalMerkleLedger(), LedgerScheme)

    def test_add_and_verify(self) -> None:
        scheme = LocalMerkleLedger()
        scheme.add_record_hash("hash-1")
        scheme.add_record_hash("hash-2")
        assert scheme.verify()

    def test_root_hash_changes(self) -> None:
        scheme = LocalMerkleLedger()
        scheme.add_record_hash("hash-1")
        root1 = scheme.root_hash
        scheme.add_record_hash("hash-2")
        root2 = scheme.root_hash
        assert root1 != root2

    def test_proof_verifies(self) -> None:
        scheme = LocalMerkleLedger()
        for i in range(5):
            scheme.add_record_hash(f"hash-{i}")
        proof = scheme.get_proof(2)
        assert proof.verify()

    def test_status(self) -> None:
        scheme = LocalMerkleLedger()
        scheme.add_record_hash("a" * 64)
        status = scheme.get_status()
        assert status["scheme"] == "local_merkle"
        assert status["leaf_count"] == 1
        assert status["tree_valid"] is True
        assert status["root_hash"] != ""

    def test_empty_root_hash(self) -> None:
        scheme = LocalMerkleLedger()
        assert scheme.root_hash == ""

    def test_empty_verify(self) -> None:
        scheme = LocalMerkleLedger()
        assert scheme.verify()


# ── ChainAnchor ──────────────────────────────────────────────────


class TestChainAnchor:
    def test_create_anchor(self) -> None:
        anchor = ChainAnchor(merkle_root="abc123", record_count=10)
        assert anchor.merkle_root == "abc123"
        assert anchor.record_count == 10

    def test_compute_hash(self) -> None:
        anchor = ChainAnchor(merkle_root="abc123", record_count=10)
        h = anchor.compute_hash()
        assert len(h) == 64

    def test_deterministic_hash(self) -> None:
        from datetime import datetime, timezone

        fixed_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        a1 = ChainAnchor(
            anchor_id="a1",
            merkle_root="root",
            record_count=5,
            chain_name="test",
            timestamp=fixed_ts,
        )
        a2 = ChainAnchor(
            anchor_id="a1",
            merkle_root="root",
            record_count=5,
            chain_name="test",
            timestamp=fixed_ts,
        )
        assert a1.compute_hash() == a2.compute_hash()

    def test_to_dict(self) -> None:
        anchor = ChainAnchor(merkle_root="abc", record_count=3)
        d = anchor.to_dict()
        assert d["merkle_root"] == "abc"
        assert d["record_count"] == 3


# ── InMemoryAnchorBackend ────────────────────────────────────────


class TestInMemoryAnchorBackend:
    def test_commit_and_verify(self) -> None:
        backend = InMemoryAnchorBackend(chain_name="test-chain")
        anchor = ChainAnchor(merkle_root="root123", record_count=10)
        tx_id = backend.commit(anchor)
        assert tx_id.startswith("test-chain:tx:")
        assert backend.verify_anchor(anchor)

    def test_verify_nonexistent(self) -> None:
        backend = InMemoryAnchorBackend()
        anchor = ChainAnchor(merkle_root="nope")
        assert not backend.verify_anchor(anchor)

    def test_get_latest_anchor(self) -> None:
        backend = InMemoryAnchorBackend()
        assert backend.get_latest_anchor() is None

        a1 = ChainAnchor(merkle_root="r1")
        a2 = ChainAnchor(merkle_root="r2")
        backend.commit(a1)
        backend.commit(a2)
        latest = backend.get_latest_anchor()
        assert latest is not None
        assert latest.merkle_root == "r2"

    def test_anchor_count(self) -> None:
        backend = InMemoryAnchorBackend()
        assert backend.anchor_count == 0
        backend.commit(ChainAnchor(merkle_root="r1"))
        assert backend.anchor_count == 1

    def test_get_all_anchors(self) -> None:
        backend = InMemoryAnchorBackend()
        for i in range(3):
            backend.commit(ChainAnchor(merkle_root=f"root-{i}"))
        all_a = backend.get_all_anchors()
        assert len(all_a) == 3


# ── BlockchainAnchoredLedger ─────────────────────────────────────


class TestBlockchainAnchoredLedger:
    def test_scheme_type(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(anchor_backend=backend)
        assert scheme.scheme_type == LedgerSchemeType.BLOCKCHAIN_ANCHORED

    def test_satisfies_protocol(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(anchor_backend=backend)
        assert isinstance(scheme, LedgerScheme)

    def test_auto_anchor_at_interval(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=5
        )
        for i in range(12):
            scheme.add_record_hash(f"h{i}")
        # Should have anchored at 5 and 10
        assert len(scheme.anchors) == 2
        assert scheme.anchors[0].record_count == 5
        assert scheme.anchors[1].record_count == 10

    def test_manual_anchor(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=0
        )
        for i in range(3):
            scheme.add_record_hash(f"h{i}")
        assert len(scheme.anchors) == 0

        anchor = scheme.anchor_now()
        assert anchor.record_count == 3
        assert len(scheme.anchors) == 1

    def test_verify(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(anchor_backend=backend)
        for i in range(5):
            scheme.add_record_hash(f"h{i}")
        assert scheme.verify()

    def test_proof(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(anchor_backend=backend)
        for i in range(5):
            scheme.add_record_hash(f"h{i}")
        proof = scheme.get_proof(2)
        assert proof.verify()

    def test_verify_anchors(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=3
        )
        for i in range(6):
            scheme.add_record_hash(f"h{i}")
        assert scheme.verify_anchors()

    def test_anchor_chaining(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=3
        )
        for i in range(9):
            scheme.add_record_hash(f"h{i}")
        anchors = scheme.anchors
        assert len(anchors) == 3
        # First anchor has no predecessor
        assert anchors[0].previous_anchor_id == ""
        # Second links to first
        assert anchors[1].previous_anchor_id == anchors[0].anchor_id
        # Third links to second
        assert anchors[2].previous_anchor_id == anchors[1].anchor_id

    def test_status(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=10
        )
        for i in range(5):
            scheme.add_record_hash(f"h{i}")
        status = scheme.get_status()
        assert status["scheme"] == "blockchain_anchored"
        assert status["leaf_count"] == 5
        assert status["anchor_count"] == 0
        assert status["records_since_anchor"] == 5
        assert status["anchor_interval"] == 10

    def test_latest_anchor(self) -> None:
        backend = InMemoryAnchorBackend()
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=0
        )
        assert scheme.latest_anchor is None
        scheme.add_record_hash("h1")
        scheme.anchor_now()
        assert scheme.latest_anchor is not None


# ── Extended Action Types ─────────────────────────────────────────


class TestExtendedActionTypes:
    def test_new_actions_exist(self) -> None:
        assert ProvenanceAction.MODEL_INVOKED.value == "model_invoked"
        assert ProvenanceAction.DATASET_ACCESSED.value == "dataset_accessed"
        assert ProvenanceAction.OUTCOME_RECORDED.value == "outcome_recorded"
        assert ProvenanceAction.CHAIN_ANCHORED.value == "chain_anchored"
        assert ProvenanceAction.LEDGER_VERIFIED.value == "ledger_verified"

    def test_new_actions_roundtrip(self) -> None:
        for action in [
            ProvenanceAction.MODEL_INVOKED,
            ProvenanceAction.DATASET_ACCESSED,
            ProvenanceAction.OUTCOME_RECORDED,
            ProvenanceAction.CHAIN_ANCHORED,
            ProvenanceAction.LEDGER_VERIFIED,
        ]:
            assert ProvenanceAction(action.value) is action


# ── Ledger with Scheme Integration ───────────────────────────────


class TestLedgerSchemeIntegration:
    def test_ledger_with_local_scheme(self) -> None:
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        scheme = LocalMerkleLedger()
        ledger = ProvenanceLedger(scheme=scheme)

        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent-1",
            resource_id="calc",
        )
        ledger.record(
            action=ProvenanceAction.MODEL_INVOKED,
            actor_id="agent-1",
            resource_id="gpt-4",
        )

        assert ledger.record_count == 2
        assert ledger.verify_chain()
        assert scheme.verify()
        assert ledger.scheme is scheme

    def test_ledger_with_blockchain_scheme(self) -> None:
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        backend = InMemoryAnchorBackend(chain_name="eth-testnet")
        scheme = BlockchainAnchoredLedger(
            anchor_backend=backend, anchor_interval=3
        )
        ledger = ProvenanceLedger(scheme=scheme)

        for i in range(5):
            ledger.record(
                action=ProvenanceAction.DATASET_ACCESSED,
                actor_id="agent-1",
                resource_id=f"dataset-{i}",
            )

        assert ledger.record_count == 5
        assert ledger.verify_chain()
        assert len(scheme.anchors) == 1  # anchored at 3

    def test_scheme_status(self) -> None:
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        scheme = LocalMerkleLedger()
        ledger = ProvenanceLedger(scheme=scheme)
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="a",
            resource_id="r",
        )

        status = ledger.get_scheme_status()
        assert status["scheme"] == "local_merkle"
        assert status["leaf_count"] == 1

    def test_no_scheme_status(self) -> None:
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        ledger = ProvenanceLedger()
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="a",
            resource_id="r",
        )

        status = ledger.get_scheme_status()
        assert status["scheme"] == "internal_merkle"
        assert status["leaf_count"] == 1

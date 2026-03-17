"""Tests for provenance export and verification utilities."""

from __future__ import annotations

import pytest

from fastmcp.server.security.provenance.export import (
    VerificationBundle,
    export_chain_dump,
    verify_bundle,
    verify_chain_dump,
)
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.provenance.records import ProvenanceAction


@pytest.fixture
def populated_ledger() -> ProvenanceLedger:
    """Create a ledger with several records."""
    ledger = ProvenanceLedger(ledger_id="test-export")
    for i in range(5):
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id=f"agent-{i % 2}",
            resource_id=f"tool-{i}",
            input_data={"arg": i},
        )
    return ledger


class TestExportVerificationBundle:
    def test_export_bundle(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[2]
        bundle = populated_ledger.export_verification_bundle(record.record_id)

        assert "record" in bundle
        assert "merkle_proof" in bundle
        assert "chain_context" in bundle
        assert "ledger_state" in bundle
        assert bundle["record"]["record_id"] == record.record_id

    def test_export_bundle_not_found(self, populated_ledger: ProvenanceLedger) -> None:
        with pytest.raises(KeyError, match="not found"):
            populated_ledger.export_verification_bundle("nonexistent")

    def test_verify_exported_bundle(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[2]
        bundle = populated_ledger.export_verification_bundle(record.record_id)
        result = verify_bundle(bundle)

        assert result["valid"] is True
        assert result["checks"]["record_hash_matches_leaf"] is True
        assert result["checks"]["merkle_proof_valid"] is True
        assert result["checks"]["chain_link_consistent"] is True

    def test_verify_first_record(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[0]
        bundle = populated_ledger.export_verification_bundle(record.record_id)
        result = verify_bundle(bundle)
        assert result["valid"] is True

    def test_verify_last_record(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[-1]
        bundle = populated_ledger.export_verification_bundle(record.record_id)
        result = verify_bundle(bundle)
        assert result["valid"] is True

    def test_tampered_bundle_detected(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[2]
        bundle = populated_ledger.export_verification_bundle(record.record_id)

        # Tamper with the record
        bundle["record"]["actor_id"] = "tampered-actor"

        result = verify_bundle(bundle)
        assert result["valid"] is False
        assert result["checks"]["record_hash_matches_leaf"] is False

    def test_tampered_proof_detected(self, populated_ledger: ProvenanceLedger) -> None:
        record = populated_ledger.all_records[2]
        bundle = populated_ledger.export_verification_bundle(record.record_id)

        # Tamper with a proof hash
        if bundle["merkle_proof"]["proof_hashes"]:
            bundle["merkle_proof"]["proof_hashes"][0] = "0" * 64

        result = verify_bundle(bundle)
        assert result["valid"] is False
        assert result["checks"]["merkle_proof_valid"] is False


class TestExportChainDump:
    def test_export_full_chain(self, populated_ledger: ProvenanceLedger) -> None:
        dump = export_chain_dump(
            records=populated_ledger.all_records,
            root_hash=populated_ledger.root_hash,
        )

        assert dump["format"] == "securemcp-provenance-export-v1"
        assert dump["record_count"] == 5
        assert len(dump["records"]) == 5
        assert len(dump["merkle_root"]) == 64
        assert len(dump["chain_digest"]) == 64

    def test_export_empty_chain(self) -> None:
        dump = export_chain_dump(records=[], root_hash="")
        assert dump["record_count"] == 0
        assert dump["chain_digest"] == ""

    def test_verify_exported_chain(self, populated_ledger: ProvenanceLedger) -> None:
        dump = export_chain_dump(
            records=populated_ledger.all_records,
            root_hash=populated_ledger.root_hash,
        )
        result = verify_chain_dump(dump)

        assert result["valid"] is True
        assert result["chain_intact"] is True
        assert result["hashes_valid"] is True
        assert result["record_count"] == 5

    def test_verify_empty_chain(self) -> None:
        dump = export_chain_dump(records=[], root_hash="")
        result = verify_chain_dump(dump)
        assert result["valid"] is True

    def test_detect_broken_chain(self, populated_ledger: ProvenanceLedger) -> None:
        dump = export_chain_dump(
            records=populated_ledger.all_records,
            root_hash=populated_ledger.root_hash,
        )

        # Tamper with the previous_hash of record 2
        dump["records"][2]["previous_hash"] = "tampered"

        result = verify_chain_dump(dump)
        assert result["valid"] is False
        assert result["chain_intact"] is False
        assert 2 in result["broken_links"]

    def test_detect_hash_mismatch(self, populated_ledger: ProvenanceLedger) -> None:
        dump = export_chain_dump(
            records=populated_ledger.all_records,
            root_hash=populated_ledger.root_hash,
        )

        # Tamper with the actor_id but not the computed_hash
        dump["records"][1]["actor_id"] = "tampered"

        result = verify_chain_dump(dump)
        assert result["valid"] is False
        assert result["hashes_valid"] is False
        assert 1 in result["recompute_failures"]


class TestVerificationBundleDataclass:
    def test_to_dict(self) -> None:
        bundle = VerificationBundle(
            record={"record_id": "test"},
            proof_leaf_hash="leaf",
            proof_hashes=["h1", "h2"],
            proof_directions=["left", "right"],
            proof_root_hash="root",
            chain_predecessor_hash="prev",
            chain_successor_hash="next",
            ledger_root_hash="lroot",
            ledger_record_count=10,
        )
        d = bundle.to_dict()
        assert d["record"]["record_id"] == "test"
        assert d["merkle_proof"]["leaf_hash"] == "leaf"
        assert len(d["merkle_proof"]["proof_hashes"]) == 2
        assert d["chain_context"]["predecessor_hash"] == "prev"
        assert d["ledger_state"]["record_count"] == 10

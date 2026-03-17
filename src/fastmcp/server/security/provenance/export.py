"""Provenance export and verification utilities.

Provides tools for exporting ledger data in auditor-friendly formats,
generating verification bundles with Merkle proofs, and validating
exported data independently of the running system.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastmcp.server.security.provenance.merkle import MerkleProof
from fastmcp.server.security.provenance.records import ProvenanceRecord


@dataclass(frozen=True)
class VerificationBundle:
    """A self-contained bundle for independently verifying a record.

    Contains the record, its Merkle proof, the chain context
    (predecessor and successor hashes), and the ledger root hash
    at the time of export. An external auditor can verify:

    1. The record hash matches the Merkle proof leaf.
    2. The Merkle proof is valid against the root hash.
    3. The chain link (previous_hash) is consistent.

    Attributes:
        record: The provenance record being verified.
        proof: Merkle inclusion proof for the record.
        chain_predecessor_hash: Hash of the record before this one.
        chain_successor_hash: Hash of the record after this one (if any).
        ledger_root_hash: Merkle root at time of export.
        ledger_record_count: Total records in ledger at export time.
        exported_at: When this bundle was created.
    """

    record: dict[str, Any] = field(default_factory=dict)
    proof_leaf_hash: str = ""
    proof_hashes: list[str] = field(default_factory=list)
    proof_directions: list[str] = field(default_factory=list)
    proof_root_hash: str = ""
    chain_predecessor_hash: str = ""
    chain_successor_hash: str = ""
    ledger_root_hash: str = ""
    ledger_record_count: int = 0
    exported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON export."""
        return {
            "record": self.record,
            "merkle_proof": {
                "leaf_hash": self.proof_leaf_hash,
                "proof_hashes": self.proof_hashes,
                "directions": self.proof_directions,
                "root_hash": self.proof_root_hash,
            },
            "chain_context": {
                "predecessor_hash": self.chain_predecessor_hash,
                "successor_hash": self.chain_successor_hash,
            },
            "ledger_state": {
                "root_hash": self.ledger_root_hash,
                "record_count": self.ledger_record_count,
            },
            "exported_at": self.exported_at.isoformat(),
        }


def verify_bundle(bundle_data: dict[str, Any]) -> dict[str, Any]:
    """Independently verify an exported verification bundle.

    This function can be run completely offline — it does not need
    access to the running ledger. It reconstructs the Merkle proof
    and checks consistency.

    Args:
        bundle_data: A dict from ``VerificationBundle.to_dict()``.

    Returns:
        A dict with verification results::

            {
                "valid": True/False,
                "checks": {
                    "record_hash_matches_leaf": True/False,
                    "merkle_proof_valid": True/False,
                    "chain_link_consistent": True/False,
                },
                "record_id": "...",
                "details": "..."
            }
    """
    checks: dict[str, bool] = {}
    details: list[str] = []

    record = bundle_data.get("record", {})
    proof_data = bundle_data.get("merkle_proof", {})
    chain_ctx = bundle_data.get("chain_context", {})

    record_id = record.get("record_id", "unknown")

    # 1. Recompute record hash and compare to proof leaf
    try:
        rec = _reconstruct_record(record)
        computed_hash = rec.compute_hash()
        leaf_hash = proof_data.get("leaf_hash", "")
        checks["record_hash_matches_leaf"] = computed_hash == leaf_hash
        if not checks["record_hash_matches_leaf"]:
            details.append(
                f"Record hash mismatch: computed={computed_hash[:16]}... "
                f"leaf={leaf_hash[:16]}..."
            )
    except Exception as exc:
        checks["record_hash_matches_leaf"] = False
        details.append(f"Could not reconstruct record: {exc}")

    # 2. Verify Merkle proof
    try:
        proof = MerkleProof(
            leaf_hash=proof_data.get("leaf_hash", ""),
            proof_hashes=proof_data.get("proof_hashes", []),
            directions=proof_data.get("directions", []),
            root_hash=proof_data.get("root_hash", ""),
        )
        checks["merkle_proof_valid"] = proof.verify()
        if not checks["merkle_proof_valid"]:
            details.append("Merkle proof verification failed")
    except Exception as exc:
        checks["merkle_proof_valid"] = False
        details.append(f"Merkle proof error: {exc}")

    # 3. Check chain link consistency
    predecessor = chain_ctx.get("predecessor_hash", "")
    record_prev = record.get("previous_hash", "")
    if predecessor and record_prev:
        checks["chain_link_consistent"] = predecessor == record_prev
        if not checks["chain_link_consistent"]:
            details.append("Chain predecessor does not match record.previous_hash")
    else:
        checks["chain_link_consistent"] = True  # No chain context to check

    all_valid = all(checks.values())

    return {
        "valid": all_valid,
        "checks": checks,
        "record_id": record_id,
        "details": "; ".join(details) if details else "All checks passed",
    }


def export_chain_dump(
    records: list[ProvenanceRecord],
    root_hash: str,
) -> dict[str, Any]:
    """Export a complete chain dump for external audit.

    Args:
        records: All records from the ledger.
        root_hash: Current Merkle root hash.

    Returns:
        A JSON-safe dict containing the full chain with
        integrity metadata.
    """
    chain_records = []
    for rec in records:
        chain_records.append(
            {
                **rec.to_dict(),
                "computed_hash": rec.compute_hash(),
            }
        )

    # Compute overall chain digest
    chain_digest = ""
    if chain_records:
        digest_payload = json.dumps(
            [r["computed_hash"] for r in chain_records],
            separators=(",", ":"),
        )
        chain_digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()

    return {
        "format": "securemcp-provenance-export-v1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "merkle_root": root_hash,
        "chain_digest": chain_digest,
        "records": chain_records,
    }


def verify_chain_dump(dump: dict[str, Any]) -> dict[str, Any]:
    """Verify an exported chain dump offline.

    Reconstructs and verifies the hash chain from the exported records.

    Args:
        dump: A dict from ``export_chain_dump()``.

    Returns:
        Verification result dict.
    """
    records = dump.get("records", [])
    if not records:
        return {
            "valid": True,
            "record_count": 0,
            "chain_intact": True,
            "details": "Empty chain",
        }

    broken_links: list[int] = []

    # Verify genesis
    if records[0].get("previous_hash") != "genesis":
        broken_links.append(0)

    # Verify sequential links
    for i in range(1, len(records)):
        expected_prev = records[i - 1].get("computed_hash", "")
        actual_prev = records[i].get("previous_hash", "")
        if expected_prev != actual_prev:
            broken_links.append(i)

    # Verify each record's computed_hash
    recompute_failures: list[int] = []
    for i, raw in enumerate(records):
        try:
            rec = _reconstruct_record(raw)
            if rec.compute_hash() != raw.get("computed_hash", ""):
                recompute_failures.append(i)
        except Exception:
            recompute_failures.append(i)

    chain_intact = len(broken_links) == 0 and len(recompute_failures) == 0

    return {
        "valid": chain_intact,
        "record_count": len(records),
        "chain_intact": len(broken_links) == 0,
        "hashes_valid": len(recompute_failures) == 0,
        "broken_links": broken_links,
        "recompute_failures": recompute_failures,
        "details": "All checks passed"
        if chain_intact
        else f"{len(broken_links)} broken links, {len(recompute_failures)} hash mismatches",
    }


def _reconstruct_record(data: dict[str, Any]) -> ProvenanceRecord:
    """Reconstruct a ProvenanceRecord from a dict for hash verification."""
    from fastmcp.server.security.storage.serialization import (
        provenance_record_from_dict,
    )

    return provenance_record_from_dict(data)

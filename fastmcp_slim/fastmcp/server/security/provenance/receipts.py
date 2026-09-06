"""Portable execution receipts backed by the provenance ledger.

Proofs establish integrity relative to a ledger root, not issuer authenticity.
Consumers should obtain a trusted root independently when authenticity matters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fastmcp.server.security.provenance.export import verify_bundle
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.provenance.records import ProvenanceAction, hash_data

RECEIPT_META_KEY = "securemcp/execution-receipt"


class ExecutionReceiptClaims(BaseModel):
    """Versioned claims; all fields are committed to the ledger hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    ledger_id: str
    actor_id: str
    tool_name: str
    status: Literal["success", "error"]
    started_at: str
    completed_at: str
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    digest_algorithm: Literal["sha256"] = "sha256"
    input_scope: Literal["redacted-tool-request"] = "redacted-tool-request"
    output_scope: Literal["tool-result-or-error-type"] = "tool-result-or-error-type"


class ExecutionReceipt(BaseModel):
    """Dedicated portable object returned in MCP result metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claims: ExecutionReceiptClaims
    proof: dict[str, Any]


def issue_execution_receipt(
    ledger: ProvenanceLedger,
    *,
    actor_id: str,
    tool_name: str,
    status: Literal["success", "error"],
    started_at: datetime,
    completed_at: datetime,
    input_data: Any,
    output_data: Any,
) -> ExecutionReceipt:
    """Persist hash-bound claims and return their inclusion proof."""
    claims = ExecutionReceiptClaims(
        ledger_id=ledger.ledger_id,
        actor_id=actor_id,
        tool_name=tool_name,
        status=status,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        input_digest=hash_data(input_data),
        output_digest=hash_data(output_data),
    )
    payload = claims.model_dump(mode="json")
    record = ledger.record(
        action=ProvenanceAction.EXECUTION_RECEIPT,
        actor_id=actor_id,
        resource_id=tool_name,
        input_data=payload,
        metadata={"execution_receipt": payload},
    )
    return ExecutionReceipt(
        claims=claims, proof=ledger.export_verification_bundle(record.record_id)
    )


def receipt_for_record(ledger: ProvenanceLedger, record_id: str) -> ExecutionReceipt:
    """Re-export an existing receipt against the current ledger root."""
    proof = ledger.export_verification_bundle(record_id)
    record = proof["record"]
    if record["action"] != ProvenanceAction.EXECUTION_RECEIPT.value:
        raise KeyError(record_id)
    receipt = ExecutionReceipt(
        claims=record["metadata"]["execution_receipt"], proof=proof
    )
    if not verify_execution_receipt(receipt.model_dump(mode="json"))["valid"]:
        raise ValueError("Stored receipt failed integrity verification")
    return receipt


def verify_execution_receipt(
    data: Any, *, trusted_root: str | None = None
) -> dict[str, Any]:
    """Verify claims and proof, optionally against an independently trusted root.

    Without a trusted root, valid means internal integrity only. This does
    not prove the identity of the issuer or the truth of the recorded outcome.
    """
    try:
        receipt = ExecutionReceipt.model_validate(data)
        claims = receipt.claims.model_dump(mode="json")
        proof = receipt.proof
        record = proof["record"]
        merkle = proof["merkle_proof"]
        checks = dict(verify_bundle(proof)["checks"])
        checks["claims_bound"] = hash_data(claims) == record["input_hash"]
        checks["execution_record"] = (
            record["action"] == ProvenanceAction.EXECUTION_RECEIPT.value
            and record["actor_id"] == receipt.claims.actor_id
            and record["resource_id"] == receipt.claims.tool_name
        )
        checks["root_consistent"] = (
            merkle["root_hash"] == proof["ledger_state"]["root_hash"]
        )
        checks["proof_shape"] = len(merkle["proof_hashes"]) == len(
            merkle["directions"]
        ) and all(d in ("left", "right") for d in merkle["directions"])
        if trusted_root is not None:
            checks["trusted_root_matches"] = merkle["root_hash"] == trusted_root
        return {
            "valid": all(checks.values()),
            "checks": checks,
            "receipt_id": receipt.claims.receipt_id,
            "trust": "trusted-root"
            if trusted_root is not None
            else "internal-integrity-only",
        }
    except (ValidationError, KeyError, TypeError, ValueError, AttributeError):
        return {"valid": False, "checks": {}, "error": "Malformed execution receipt"}

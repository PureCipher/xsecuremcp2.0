# Execution Receipts

Execution Receipts are a SecureMCP security pillar: a dedicated, portable object describing an observed tool execution, with cryptographic commitments to its inputs, output, and claims. The Provenance Ledger stores the evidence; the receipt makes that evidence available to clients and reviewers.

## Enable and consume

Enable provenance on a SecureMCP server. Completed tool calls automatically include a version 1.0 receipt under the MCP result's `_meta["securemcp/execution-receipt"]`. Normal content, structured output, and existing metadata are preserved. No output schema changes are required.

```python
from securemcp import SecureMCP, SecurityConfig
from securemcp.config import ProvenanceConfig

server = SecureMCP(
    "calculator",
    security=SecurityConfig(provenance=ProvenanceConfig()),
)

@server.tool
def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    server.run()
```

Client-side verification uses the public Python API:

```python
import asyncio
from fastmcp import Client
from securemcp.receipts import RECEIPT_META_KEY, verify_execution_receipt

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
        receipt = result.meta[RECEIPT_META_KEY]
        print(verify_execution_receipt(receipt))

asyncio.run(main())
```

## Object and integrity contract

An `ExecutionReceipt` contains `claims` and `proof`. Claims include schema version, unique receipt ID, ledger ID, caller ID, tool name, success/error outcome, UTC start/completion timestamps, SHA-256 input/output digests, and explicit digest scopes. A separate `execution_receipt` provenance record commits to the complete claims object in its `input_hash`; the claims are also stored in record metadata for retrieval. This avoids relying on provenance metadata itself being hash-covered.

The proof includes the record, Merkle inclusion proof, chain context, and root at export time. Every claim is hash-bound, including outcome and timing. Re-exporting uses the current ledger root but retains the same claims and receipt ID. The original inline proof remains verifiable against its original root after more records are appended. The receipt ID identifies the execution artifact; the proof's record ID identifies its ledger entry and is used by the export endpoint.

Input digests cover `{"tool": tool_name, "arguments": redacted_arguments}` using the existing recursive credential-field redaction. They intentionally do not establish equality of redacted secrets. Output digests cover `{"content": [...], "structured_content": ..., "is_error": bool}`, with content blocks serialized using JSON mode and protocol aliases. Receipt metadata is excluded to avoid circular hashing. Raw request and result content is not persisted in receipts. Digests are commitments, not encryption; low-entropy values can still be guessed.

`verify_execution_receipt(receipt)` checks internal consistency. To bind verification to a root obtained through a trusted channel, use `verify_execution_receipt(receipt, trusted_root=expected_root)`. A self-consistent proof alone does not authenticate the issuer or prove that a reported outcome is true. Version 1 does not provide issuer signatures or external anchoring automatically.

## Coverage and lifecycle

- Both successful tool results and returned `is_error` results carry receipts.
- Raised exceptions retain their original protocol behavior. Their error receipts are stored for API retrieval; their output digest covers only `{"error_type": exception_class_name}`. Exception messages are not included in the receipt.
- Calls rejected by middleware before provenance runs have no execution receipt. An execution receipt is not a claim that every security control ran or approved the call.
- A multi-step call returning `InputRequiredToolResult` is awaiting input, not a completed execution, and does not issue a completion receipt for that leg.
- Resources, prompts, and listing operations retain their existing provenance behavior; this receipt version covers tool executions.
- Disabling provenance or explicitly bypassing the transport disables receipt issuance too.
- Receipts share the configured ledger's persistence and retention. In-memory ledgers do not survive restart; configure a persistent provenance backend when retention is required.
- Issuance adds a separate ledger entry per completed tool call. Existing tool-call records remain available for metrics and audit consumers; execution counts should filter by action, not count all ledger entries.

## Security API

Routes are mounted with the existing security API and require its authenticated read capability. They have the same governance visibility as provenance queries; these are not public per-caller download URLs.

| Route | Behavior |
| --- | --- |
| `GET /security/receipts?actor=...&tool=...&limit=50` | Latest receipts, newest first; limit 1–200 |
| `GET /security/receipts/{record_id}` | Export the receipt associated with a ledger record |
| `POST /security/receipts/verify` | Verify `{"receipt": {...}, "trusted_root": "optional root"}` |

Malformed queries return 400, missing receipts 404, corrupt stored receipts 409, and an unavailable provenance ledger 503. Verification of an invalid artifact returns a result with `valid: false`. Verification does not require a local ledger.

## xregistry

The companion xregistry console exposes **Execution Receipts** as a governance destination and a security pillar. Reviewers can filter the latest 100 receipts by tool, caller, receipt ID, or outcome, inspect their JSON, verify integrity, and download portable JSON artifacts.

This workspace reads receipts from the connected backend's ledger. Catalog-only upstream servers execute outside that backend and are not automatically observed. Supporting those deployments later requires authenticated receipt ingestion, issuer identity/signature verification or trusted root registration, listing-to-issuer binding, and explicit retention/access rules. A listing's presence or certification must not be presented as proof that a runtime receipt exists.

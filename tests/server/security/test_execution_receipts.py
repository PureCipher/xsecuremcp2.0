"""Execution receipt integrity, transport, persistence, and API regressions."""

from copy import deepcopy
from datetime import datetime, timezone

import mcp.types as mt
import pytest
from starlette.testclient import TestClient

from fastmcp import Client, FastMCP
from fastmcp.server.middleware.middleware import MiddlewareContext
from fastmcp.server.security import attach_security
from fastmcp.server.security.config import ProvenanceConfig, SecurityConfig
from fastmcp.server.security.http import SecurityAPI, mount_security_routes
from fastmcp.server.security.middleware.provenance_recording import (
    ProvenanceRecordingMiddleware,
)
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.provenance.receipts import (
    RECEIPT_META_KEY,
    issue_execution_receipt,
    receipt_for_record,
    verify_execution_receipt,
)
from fastmcp.server.security.provenance.records import ProvenanceAction, hash_data
from fastmcp.server.security.storage.memory import MemoryBackend
from fastmcp.tools.base import ToolResult


def issue(ledger):
    now = datetime.now(timezone.utc)
    return issue_execution_receipt(
        ledger,
        actor_id="alice",
        tool_name="add",
        status="success",
        started_at=now,
        completed_at=now,
        input_data={"a": 1},
        output_data={"answer": 2},
    )


def test_receipt_round_trip_and_trusted_root():
    ledger = ProvenanceLedger()
    receipt = issue(ledger).model_dump(mode="json")
    assert verify_execution_receipt(receipt)["valid"]
    assert verify_execution_receipt(receipt, trusted_root=ledger.root_hash)["valid"]
    assert not verify_execution_receipt(receipt, trusted_root="0" * 64)["valid"]
    issue(ledger)
    assert verify_execution_receipt(receipt)["valid"]
    restored = receipt_for_record(ledger, receipt["proof"]["record"]["record_id"])
    assert restored.claims.model_dump() == receipt["claims"]
    assert verify_execution_receipt(
        restored.model_dump(), trusted_root=ledger.root_hash
    )["valid"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "error"),
        ("tool_name", "delete"),
        ("actor_id", "mallory"),
        ("input_digest", "0" * 64),
        ("output_digest", "0" * 64),
        ("ledger_id", "forged"),
        ("receipt_id", "forged"),
        ("completed_at", "forged"),
    ],
)
def test_every_claim_is_hash_bound(field, value):
    receipt = issue(ProvenanceLedger()).model_dump()
    receipt["claims"][field] = value
    assert not verify_execution_receipt(receipt)["valid"]


@pytest.mark.parametrize(
    "data", [None, [], {}, {"claims": None, "proof": {}}, {"claims": {}, "proof": []}]
)
def test_malformed_receipts_fail_closed(data):
    assert not verify_execution_receipt(data)["valid"]


def test_proof_tampering():
    receipt = issue(ProvenanceLedger()).model_dump()
    corrupt = deepcopy(receipt)
    corrupt["proof"]["ledger_state"]["root_hash"] = "0" * 64
    assert not verify_execution_receipt(corrupt)["valid"]
    receipt["proof"]["merkle_proof"]["directions"].append("left")
    assert not verify_execution_receipt(receipt)["valid"]


def test_receipt_persistence_and_metadata_tampering():
    backend = MemoryBackend()
    ledger = ProvenanceLedger(backend=backend)
    receipt = issue(ledger)
    restored = ProvenanceLedger(backend=backend)
    record_id = receipt.proof["record"]["record_id"]
    assert receipt_for_record(restored, record_id).claims == receipt.claims
    record = restored.get_record(record_id)
    assert record is not None
    record.metadata["execution_receipt"]["status"] = "error"
    with pytest.raises(ValueError, match="integrity"):
        receipt_for_record(restored, record_id)


@pytest.mark.parametrize(
    "raw,is_error", [(False, False), (False, True), (True, False), (True, True)]
)
async def test_middleware_preserves_result_and_hashes_output(raw, is_error):
    ledger = ProvenanceLedger()
    middleware = ProvenanceRecordingMiddleware(ledger)
    original = ToolResult(
        content="answer",
        structured_content={"answer": 2},
        meta={"custom": "kept"},
        is_error=is_error,
    )
    if raw:
        wire = original.to_mcp_result()
        assert isinstance(wire, mt.CallToolResult)
        original = ToolResult.from_mcp_result(wire)

    async def next_call(context):
        return original

    context = MiddlewareContext(
        message=mt.CallToolRequestParams(
            name="add", arguments={"token": "secret", "a": 1}
        )
    )
    result = await middleware.on_call_tool(context, next_call)
    assert result.meta is not None
    receipt = result.meta[RECEIPT_META_KEY]
    assert verify_execution_receipt(receipt)["valid"]
    assert receipt["claims"]["status"] == ("error" if is_error else "success")
    assert result.content == original.content
    assert result.structured_content == original.structured_content
    assert result.meta["custom"] == "kept"
    assert original.meta is not None
    assert RECEIPT_META_KEY not in original.meta
    wire = result.to_mcp_result()
    assert isinstance(wire, mt.CallToolResult)
    assert wire.meta is not None
    assert wire.meta[RECEIPT_META_KEY] == receipt
    assert receipt["claims"]["input_digest"] == hash_data(
        {"tool": "add", "arguments": {"token": "[REDACTED]", "a": 1}}
    )
    expected_output = {
        "content": [b.model_dump(mode="json", by_alias=True) for b in original.content],
        "structured_content": original.structured_content,
        "is_error": is_error,
    }
    assert receipt["claims"]["output_digest"] == hash_data(expected_output)
    assert "secret" not in str(receipt)


async def test_exception_keeps_original_error_and_stores_receipt():
    ledger = ProvenanceLedger()
    middleware = ProvenanceRecordingMiddleware(ledger)
    failure = RuntimeError("private payload")

    async def next_call(context):
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await middleware.on_call_tool(
            MiddlewareContext(message=mt.CallToolRequestParams(name="fail")), next_call
        )
    assert caught.value is failure
    records = ledger.get_records(action=ProvenanceAction.EXECUTION_RECEIPT)
    assert len(records) == 1
    receipt = receipt_for_record(ledger, records[0].record_id)
    assert receipt.claims.status == "error"
    assert "private payload" not in str(receipt.model_dump())


async def test_receipt_reaches_mcp_client():
    server = FastMCP("receipts")
    attach_security(server, SecurityConfig(provenance=ProvenanceConfig()))

    @server.tool
    def add(a: int) -> int:
        return a + 1

    async with Client(server) as client:
        result = await client.call_tool("add", {"a": 2})
    assert result.data == 3
    assert verify_execution_receipt(result.meta[RECEIPT_META_KEY])["valid"]


def api_client(ledger):
    server = FastMCP("receipts-api")
    mount_security_routes(
        server, api=SecurityAPI(provenance_ledger=ledger), bearer_token="test-secret"
    )
    return TestClient(server.http_app())


def test_http_auth_query_export_verify_and_errors():
    ledger = ProvenanceLedger()
    receipt = issue(ledger).model_dump(mode="json")
    headers = {"Authorization": "Bearer test-secret"}
    with api_client(ledger) as client:
        assert client.get("/security/receipts").status_code == 401
        response = client.get("/security/receipts", headers=headers)
        assert response.status_code == 200
        assert response.json()["receipts"][0]["claims"] == receipt["claims"]
        assert (
            client.get("/security/receipts?actor=bob", headers=headers).json()[
                "receipts"
            ]
            == []
        )
        for limit in ["bad", "0", "201"]:
            assert (
                client.get(
                    f"/security/receipts?limit={limit}", headers=headers
                ).status_code
                == 400
            )
        record_id = receipt["proof"]["record"]["record_id"]
        assert (
            client.get(f"/security/receipts/{record_id}", headers=headers).status_code
            == 200
        )
        assert (
            client.get("/security/receipts/missing", headers=headers).status_code == 404
        )
        assert client.post(
            "/security/receipts/verify", json={"receipt": receipt}, headers=headers
        ).json()["valid"]
        assert (
            client.post(
                "/security/receipts/verify", content="bad", headers=headers
            ).status_code
            == 400
        )
    with api_client(None) as client:
        assert client.get("/security/receipts", headers=headers).status_code == 503


def test_sqlite_receipts_survive_restart(tmp_path):
    from fastmcp.server.security.storage.sqlite import SQLiteBackend

    path = str(tmp_path / "receipts.db")
    backend = SQLiteBackend(path)
    receipt = issue(ProvenanceLedger(backend=backend))
    backend.close()
    reopened = SQLiteBackend(path)
    try:
        ledger = ProvenanceLedger(backend=reopened)
        exported = receipt_for_record(ledger, receipt.proof["record"]["record_id"])
        assert exported.claims == receipt.claims
        assert verify_execution_receipt(exported.model_dump())["valid"]
    finally:
        reopened.close()


async def test_input_required_is_not_reported_as_completed():
    import mcp_types

    from fastmcp.tools.base import InputRequiredToolResult

    ledger = ProvenanceLedger()
    middleware = ProvenanceRecordingMiddleware(ledger)
    pending = InputRequiredToolResult(
        mcp_types.InputRequiredResult(
            result_type="input_required", request_state="pending"
        )
    )

    async def next_call(context):
        return pending

    result = await middleware.on_call_tool(
        MiddlewareContext(message=mt.CallToolRequestParams(name="ask")), next_call
    )
    assert result is pending
    assert ledger.get_records(action=ProvenanceAction.EXECUTION_RECEIPT) == []


async def test_concurrent_calls_have_distinct_valid_receipts():
    import asyncio

    ledger = ProvenanceLedger()
    middleware = ProvenanceRecordingMiddleware(ledger)
    cached = ToolResult(content="shared")

    async def next_call(context):
        await asyncio.sleep(0)
        return cached

    context = MiddlewareContext(message=mt.CallToolRequestParams(name="cached"))
    results = await asyncio.gather(
        *(middleware.on_call_tool(context, next_call) for _ in range(10))
    )
    receipts = []
    for result in results:
        assert result.meta is not None
        receipts.append(result.meta[RECEIPT_META_KEY])
    assert len({r["claims"]["receipt_id"] for r in receipts}) == 10
    assert all(verify_execution_receipt(r)["valid"] for r in receipts)
    assert cached.meta is None


async def test_provenance_disabled_does_not_issue_receipts():
    server = FastMCP("no-receipts")
    attach_security(server, SecurityConfig())

    @server.tool
    def hello() -> str:
        return "hello"

    async with Client(server) as client:
        result = await client.call_tool("hello")
    assert RECEIPT_META_KEY not in (result.meta or {})

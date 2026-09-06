"""Authenticated execution receipt query, export, and verification routes."""

from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp.server.security.provenance.receipts import (
    receipt_for_record,
    verify_execution_receipt,
)
from fastmcp.server.security.provenance.records import ProvenanceAction


def mount_receipt_routes(api: Any, prefix: str, route_decorator: Any) -> None:
    """Use the security API's existing authentication and read capability gate."""

    @route_decorator(f"{prefix}/receipts", methods=["GET"])
    async def receipts_endpoint(request: Request) -> JSONResponse:
        ledger = api.provenance_ledger
        if ledger is None:
            return JSONResponse(
                {"error": "Provenance ledger not configured"}, status_code=503
            )
        try:
            limit = int(request.query_params.get("limit", "50"))
            if not 1 <= limit <= 200:
                raise ValueError
        except ValueError:
            return JSONResponse(
                {"error": "limit must be between 1 and 200"}, status_code=400
            )
        records = ledger.get_records(
            action=ProvenanceAction.EXECUTION_RECEIPT,
            actor_id=request.query_params.get("actor"),
            resource_id=request.query_params.get("tool"),
            limit=limit,
        )
        try:
            receipts = [
                receipt_for_record(ledger, r.record_id).model_dump(mode="json")
                for r in records
            ]
        except (KeyError, ValueError):
            return JSONResponse(
                {"error": "Stored receipt failed integrity verification"},
                status_code=409,
            )
        return JSONResponse(
            {
                "receipts": receipts,
                "returned": len(receipts),
                "ledger_id": ledger.ledger_id,
            }
        )

    @route_decorator(f"{prefix}/receipts/verify", methods=["POST"])
    async def verify_receipt_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse({"error": "Expected JSON"}, status_code=400)
        if not isinstance(body, dict) or "receipt" not in body:
            return JSONResponse({"error": "Expected a receipt object"}, status_code=400)
        trusted_root = body.get("trusted_root")
        if trusted_root is not None and not isinstance(trusted_root, str):
            return JSONResponse(
                {"error": "trusted_root must be a string"}, status_code=400
            )
        return JSONResponse(
            verify_execution_receipt(body["receipt"], trusted_root=trusted_root)
        )

    @route_decorator(f"{prefix}/receipts/{{record_id}}", methods=["GET"])
    async def receipt_endpoint(request: Request) -> JSONResponse:
        ledger = api.provenance_ledger
        if ledger is None:
            return JSONResponse(
                {"error": "Provenance ledger not configured"}, status_code=503
            )
        try:
            receipt = receipt_for_record(ledger, request.path_params["record_id"])
        except KeyError:
            return JSONResponse(
                {"error": "Execution receipt not found"}, status_code=404
            )
        except ValueError:
            return JSONResponse(
                {"error": "Stored receipt failed integrity verification"},
                status_code=409,
            )
        return JSONResponse(receipt.model_dump(mode="json"))

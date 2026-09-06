"""Versioned profile grants, separate from provider OAuth and live control planes."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from starlette.responses import JSONResponse

from fastmcp.server.security.consent.models import ConsentQuery
from fastmcp.server.security.middleware.contract_validation import (
    ContractValidationMiddleware,
)
from purecipher.auth import RegistryRole


def scope(profile: dict) -> dict:
    return {
        key: profile.get(key)
        for key in ("id", "owner", "purpose", "client_ids", "servers")
    }


def fingerprint(profile: dict) -> str:
    return hashlib.sha256(
        json.dumps(scope(profile), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def selected_tools(profile: dict, server: dict, client_id: str) -> list[str]:
    return server.get("client_tools", {}).get(client_id, server["tools"])


def bindings(registry: Any, profile: dict) -> list[dict]:
    broker = registry._broker_or_none()
    if broker is None:
        raise ValueError("Contract control is unavailable")
    check = ContractValidationMiddleware(broker)
    result = []
    for client_id in profile["client_ids"]:
        client = registry._client_store.get_client(client_id)
        if client is None:
            raise ValueError("A selected client is unavailable")
        contracts = sorted(
            broker.get_active_contracts_for_agent(client.slug),
            key=lambda item: item.contract_id,
        )
        for server in profile["servers"]:
            tools = selected_tools(profile, server, client_id)
            if not tools:
                continue
            contract = next(
                (
                    item
                    for item in contracts
                    if all(
                        not check._check_term_constraint(item, "call_tool", name)
                        for name in tools
                    )
                ),
                None,
            )
            if contract is None:
                raise ValueError(
                    f"Client {client.slug} needs an active SecureMCP contract covering {', '.join(tools)}"
                )
            result.append(
                {
                    "client_id": client_id,
                    "listing_id": server["listing_id"],
                    "tools": tools,
                    "contract_id": contract.contract_id,
                }
            )
    return result


def record(registry: Any, profile: dict) -> dict | None:
    return registry._workspace.get("governance-" + profile["id"])


def live_errors(registry: Any, profile: dict, grant: dict) -> list[str]:
    broker, graph = registry._broker_or_none(), registry._consent_graph_or_none()
    consent = registry._required_context().config.consent
    if broker is None or graph is None or consent is None:
        return [
            "Security approval: required contract or consent control is unavailable"
        ]
    check = ContractValidationMiddleware(broker)
    errors = []
    for binding in grant.get("bindings", []):
        client = registry._client_store.get_client(binding["client_id"])
        contract = broker.get_contract(binding["contract_id"])
        if (
            not client
            or not contract
            or not contract.is_valid()
            or contract.agent_id != client.slug
            or any(
                check._check_term_constraint(contract, "call_tool", name)
                for name in binding["tools"]
            )
        ):
            errors.append(
                "Security approval: a bound contract is expired, revoked, or no longer permits the selected tools"
            )
        if (
            client
            and not graph.evaluate(
                ConsentQuery(
                    source_id=consent.resource_owner,
                    target_id=client.slug,
                    scope="execute",
                )
            ).granted
        ):
            errors.append(
                f"Security approval: client {client.slug} needs execute consent from {consent.resource_owner}"
            )
    return list(dict.fromkeys(errors))


def blockers(registry: Any, profile: dict) -> list[str]:
    grant = record(registry, profile)
    if not grant or grant.get("fingerprint") != fingerprint(profile):
        return [
            "Security approval: review Security & access for this profile's current selections"
        ]
    errors = []
    if grant.get("status") != "approved":
        errors.append(
            "Security approval: awaiting administrator approval for this profile"
        )
    if not grant.get("owner_consented"):
        errors.append(
            "Security approval: the profile owner must confirm the selected access"
        )
    if grant.get("expires_at", 0) <= time.time():
        errors.append("Security approval: profile approval has expired")
    if not errors:
        errors.extend(live_errors(registry, profile, grant))
    return errors


def mount(registry: Any, prefix: str) -> None:
    @registry.custom_route(
        f"{prefix}/workspace/profiles/{{profile_id}}/governance",
        methods=["GET", "POST"],
    )
    async def governance(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Sign in required"}, status_code=401)
        profile = registry._workspace.get(request.path_params["profile_id"])
        admin = registry._has_roles(session, {RegistryRole.ADMIN})
        if (
            not profile
            or profile.get("kind") != "profile"
            or (profile["owner"] != session.username and not admin)
        ):
            return JSONResponse({"error": "Profile not found"}, status_code=404)
        current = record(registry, profile)
        if request.method == "GET":
            return JSONResponse(
                {
                    "profile": scope(profile),
                    "client_labels": {
                        cid: getattr(
                            registry._client_store.get_client(cid), "display_name", cid
                        )
                        for cid in profile["client_ids"]
                    },
                    "server_labels": {
                        server["listing_id"]: getattr(
                            registry._marketplace().get(server["listing_id"]),
                            "display_name",
                            None,
                        )
                        or server["listing_id"]
                        for server in profile["servers"]
                    },
                    "connection_labels": {
                        server["connection_id"]: (
                            registry._workspace.get(server["connection_id"]) or {}
                        ).get("name", "Unavailable connection")
                        for server in profile["servers"]
                        if server.get("connection_id")
                    },
                    "profile_revision": profile["revision"],
                    "approval": current,
                    "approval_current": bool(
                        current and current.get("fingerprint") == fingerprint(profile)
                    ),
                    "blockers": blockers(registry, profile),
                    "is_owner": session.username == profile["owner"],
                    "can_approve": admin,
                }
            )
        try:
            body = await request.json()
            if body.get("profile_revision") != profile["revision"] or body.get(
                "approval_revision"
            ) != (current or {}).get("revision"):
                raise ValueError(
                    "Profile or approval changed; reload before continuing"
                )
            action = body.get("action")
            owner = session.username == profile["owner"]
            if (
                action in {"request", "consent"}
                and not owner
                or action == "approve"
                and not admin
            ):
                return JSONResponse(
                    {"error": "This action is not permitted for your role"},
                    status_code=403,
                )
            if action not in {"request", "consent", "approve", "revoke"}:
                raise ValueError("Unknown action")
            if action == "request":
                if (
                    not profile.get("purpose", "").strip()
                    or not profile["servers"]
                    or not profile["client_ids"]
                ):
                    raise ValueError(
                        "Save a purpose, servers and clients before requesting approval"
                    )
                value = {
                    "id": "governance-" + profile["id"],
                    "owner": profile["owner"],
                    "kind": "profile_governance",
                    "schema_version": 1,
                    "fingerprint": fingerprint(profile),
                    "scope": scope(profile),
                    "status": "pending",
                    "owner_consented": False,
                    "bindings": [],
                    "expires_at": 0,
                }
            else:
                if not current or current["fingerprint"] != fingerprint(profile):
                    raise ValueError(
                        "Request approval for the current profile selections first"
                    )
                value = current.copy()
                if action == "consent":
                    if body.get("confirmed") is not True:
                        raise ValueError("Explicit confirmation is required")
                    value["owner_consented"] = True
                elif action == "approve":
                    if not value["owner_consented"]:
                        raise ValueError("The profile owner must confirm access first")
                    days = body.get("days", 30)
                    if type(days) is not int or not 1 <= days <= 90:
                        raise ValueError("Approval must expire in 1–90 days")
                    value["bindings"] = bindings(registry, profile)
                    errors = live_errors(registry, profile, value)
                    if errors:
                        raise ValueError("; ".join(errors))
                    value.update(
                        status="approved",
                        approved_by=session.username,
                        expires_at=time.time() + days * 86400,
                    )
                else:
                    value.update(status="revoked", owner_consented=False)
            history = list((current or {}).get("history", []))
            history.append(
                {
                    "action": action,
                    "actor": session.username,
                    "at": time.time(),
                    "fingerprint": fingerprint(profile),
                }
            )
            value["history"] = history
            saved = registry._workspace.save(value, (current or {}).get("revision"))
            ledger = registry._ledger_or_none()
            if ledger is not None:
                from fastmcp.server.security.provenance.records import ProvenanceAction

                ledger.record(
                    action=ProvenanceAction.CUSTOM,
                    actor_id=session.username,
                    resource_id=profile["id"],
                    metadata={
                        "event": "profile_governance",
                        "action": action,
                        "approval_revision": saved["revision"],
                        "scope_hash": fingerprint(profile),
                    },
                )
            return JSONResponse({"approval": saved})
        except (ValueError, TypeError, AttributeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @registry.custom_route(f"{prefix}/admin/profile-governance", methods=["GET"])
    async def queue(request):
        session = registry._session_from_request(request)
        if session is None or not registry._has_roles(session, {RegistryRole.ADMIN}):
            return JSONResponse(
                {"error": "Administrator access required"}, status_code=403
            )
        requests = []
        for item in registry._workspace.list_kind("profile_governance"):
            profile = registry._workspace.get(item["scope"]["id"])
            if profile and profile.get("kind") == "profile":
                if item["fingerprint"] != fingerprint(profile):
                    item["status"] = "scope_changed"
                elif item["status"] == "approved" and item["expires_at"] <= time.time():
                    item["status"] = "expired"
                requests.append(item)
        return JSONResponse({"requests": requests})

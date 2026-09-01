"""Authorization regressions for the SecureMCP HTTP control plane."""

from __future__ import annotations

from typing import Any, cast

import pytest
from starlette.testclient import TestClient

from fastmcp import FastMCP
from fastmcp.server.security.http import (
    SecurityAPI,
    SecurityCapability,
    mount_security_routes,
)
from fastmcp.server.security.http.authorization import principal_has_capability

_AUTH_HEADERS = {"Authorization": "Bearer valid"}


class _Contract:
    def __init__(self, *, agent_id: str, server_id: str) -> None:
        self.agent_id = agent_id
        self.server_id = server_id


class _Session:
    def __init__(self, *, agent_id: str, server_id: str) -> None:
        self.agent_id = agent_id
        self.server_id = server_id


class _Broker:
    def __init__(self) -> None:
        self.contracts: dict[str, _Contract] = {}
        self.sessions: dict[str, _Session] = {}

    def get_contract(self, contract_id: str) -> _Contract | None:
        return self.contracts.get(contract_id)

    def get_session(self, session_id: str) -> _Session | None:
        return self.sessions.get(session_id)


class _RecordingAPI:
    def __init__(self) -> None:
        self.broker = _Broker()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_dashboard(self) -> dict[str, Any]:
        self.calls.append(("dashboard", {}))
        return {"ok": True}

    def marketplace_install(
        self,
        listing_id: str,
        *,
        installer_id: str = "",
        version: str | None = None,
        verify_signature: bool = False,
    ) -> dict[str, Any]:
        data = {
            "listing_id": listing_id,
            "installer_id": installer_id,
            "version": version,
            "verify_signature": verify_signature,
        }
        self.calls.append(("marketplace_install", data))
        return data

    def marketplace_moderate(
        self,
        listing_id: str,
        *,
        moderator_id: str,
        action: str,
        reason: str = "",
    ) -> dict[str, Any]:
        data = {
            "listing_id": listing_id,
            "moderator_id": moderator_id,
            "action": action,
            "reason": reason,
        }
        self.calls.append(("marketplace_moderate", data))
        return data

    def marketplace_moderation_queue(self) -> dict[str, Any]:
        self.calls.append(("marketplace_moderation_queue", {}))
        return {"listings": []}

    async def save_policy_pack(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("save_policy_pack", dict(kwargs)))
        return {"saved": True}

    async def negotiate_contract(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("negotiate_contract", dict(body)))
        return {"accepted": True, "agent_id": body.get("agent_id")}

    async def agent_sign_contract_endpoint(
        self,
        contract_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        data = {"contract_id": contract_id, **body}
        self.calls.append(("sign_contract", data))
        return {"signed": True}

    def list_agent_contracts(self, agent_id: str) -> dict[str, Any]:
        self.calls.append(("list_agent_contracts", {"agent_id": agent_id}))
        return {"agent_id": agent_id, "contracts": []}

    def get_contract_details(self, contract_id: str) -> dict[str, Any]:
        self.calls.append(("get_contract_details", {"contract_id": contract_id}))
        return {"contract_id": contract_id}

    def get_exchange_log_entries(self, *, session_id: str | None) -> dict[str, Any]:
        self.calls.append(("get_exchange_log_entries", {"session_id": session_id}))
        return {"session_id": session_id, "entries": []}

    def grant_consent(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("grant_consent", dict(body)))
        return {"granted": True, "granted_by": body.get("granted_by")}

    def get_introspection(self, actor_id: str) -> dict[str, Any]:
        self.calls.append(("get_introspection", {"actor_id": actor_id}))
        return {"actor_id": actor_id}


def _mounted_client(
    principal: dict[str, Any],
    *,
    api: _RecordingAPI | None = None,
    authorizer: Any = None,
) -> tuple[TestClient, _RecordingAPI]:
    recording_api = api or _RecordingAPI()

    def verify(_request: Any, token: str) -> dict[str, Any] | None:
        return principal.copy() if token == "valid" else None

    server = FastMCP("authorization-test")
    mount_security_routes(
        server,
        api=cast(SecurityAPI, recording_api),
        auth_verifier=verify,
        authorizer=authorizer,
    )
    client = TestClient(server.http_app(transport="streamable-http"))
    return client, recording_api


def test_principal_without_capability_claim_can_read():
    client, api = _mounted_client({"actor": "alice"})

    response = client.get("/security/dashboard", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    assert api.calls == [("dashboard", {})]


def test_principal_without_capability_claim_cannot_administer():
    client, api = _mounted_client({"actor": "alice"})

    response = client.post(
        "/security/marketplace/listing-1/moderate",
        json={"action": "approve"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert response.json()["required_capability"] == "security:admin"
    assert api.calls == []


def test_explicit_empty_capabilities_deny_read_access():
    client, api = _mounted_client({"actor": "alice", "capabilities": []})

    response = client.get("/security/dashboard", headers=_AUTH_HEADERS)

    assert response.status_code == 403
    assert api.calls == []


def test_operate_capability_includes_read():
    principal = {"capabilities": [SecurityCapability.OPERATE.value]}

    assert principal_has_capability(principal, SecurityCapability.READ) is True


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("capabilities", ["security:operate"]),
        ("permissions", ("security:operate",)),
        ("scopes", {"security:operate"}),
        ("scope", "openid security:operate"),
        ("scp", "security:operate"),
    ],
)
def test_supported_claim_formats_grant_capabilities(claim: str, value: Any):
    principal = {claim: value}

    assert principal_has_capability(principal, SecurityCapability.OPERATE) is True


def test_admin_capability_includes_operate_and_read():
    principal = {"capabilities": ["security:admin"]}

    assert principal_has_capability(principal, SecurityCapability.OPERATE) is True
    assert principal_has_capability(principal, SecurityCapability.READ) is True


def test_operate_capability_binds_installer_to_principal():
    client, api = _mounted_client({"actor": "alice", "scope": "security:operate"})

    response = client.post(
        "/security/marketplace/listing-1/install",
        json={},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][1]["installer_id"] == "alice"


def test_operate_principal_cannot_spoof_installer():
    client, api = _mounted_client(
        {"actor": "alice", "capabilities": ["security:operate"]}
    )

    response = client.post(
        "/security/marketplace/listing-1/install",
        json={"installer_id": "mallory"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_operate_principal_cannot_use_admin_route():
    client, api = _mounted_client(
        {"actor": "alice", "permissions": ["security:operate"]}
    )

    response = client.post(
        "/security/marketplace/listing-1/moderate",
        json={"action": "approve"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_static_marketplace_moderation_route_is_admin_only():
    client, api = _mounted_client({"actor": "alice"})

    response = client.get("/security/marketplace/moderation", headers=_AUTH_HEADERS)

    assert response.status_code == 403
    assert response.json()["required_capability"] == "security:admin"
    assert api.calls == []


def test_admin_attribution_ignores_spoofed_moderator():
    client, api = _mounted_client(
        {"sub": "admin-1", "capabilities": ["security:admin"]}
    )

    response = client.post(
        "/security/marketplace/listing-1/moderate",
        json={"moderator_id": "mallory", "action": "approve"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][1]["moderator_id"] == "admin-1"


def test_static_bearer_token_remains_administrator():
    api = _RecordingAPI()
    server = FastMCP("static-admin-test")
    mount_security_routes(
        server,
        api=cast(SecurityAPI, api),
        bearer_token="static-secret",
    )
    client = TestClient(server.http_app(transport="streamable-http"))

    response = client.post(
        "/security/marketplace/listing-1/moderate",
        json={"moderator_id": "mallory", "action": "approve"},
        headers={"Authorization": "Bearer static-secret"},
    )

    assert response.status_code == 200
    assert api.calls[0][1]["moderator_id"] == "shared-secret"


def test_write_capability_requires_stable_actor_identity():
    client, api = _mounted_client({"capabilities": ["security:operate"]})

    response = client.post(
        "/security/marketplace/listing-1/install",
        json={},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert "stable principal identity" in response.json()["error"]
    assert api.calls == []


def test_custom_authorizer_receives_required_capability():
    seen: list[SecurityCapability] = []

    def authorize(
        _request: Any,
        _principal: dict[str, Any],
        required: SecurityCapability,
    ) -> bool:
        seen.append(required)
        return True

    client, api = _mounted_client({"actor": "alice"}, authorizer=authorize)

    response = client.post(
        "/security/marketplace/listing-1/moderate",
        json={"action": "approve"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert seen == [SecurityCapability.ADMIN]
    assert api.calls[0][0] == "marketplace_moderate"


def test_custom_authorizer_exception_fails_closed():
    def authorize(*_args: Any) -> bool:
        raise RuntimeError("authorization backend unavailable")

    client, api = _mounted_client({"actor": "alice"}, authorizer=authorize)

    response = client.get("/security/dashboard", headers=_AUTH_HEADERS)

    assert response.status_code == 403
    assert api.calls == []


def test_custom_authorizer_requires_exact_true_result():
    client, api = _mounted_client(
        {"actor": "alice"},
        authorizer=lambda *_args: 1,
    )

    response = client.get("/security/dashboard", headers=_AUTH_HEADERS)

    assert response.status_code == 403
    assert api.calls == []


def test_policy_write_uses_verified_principal_as_author():
    client, api = _mounted_client(
        {"actor": "policy-admin", "capabilities": ["security:admin"]}
    )

    response = client.post(
        "/security/policy/packs",
        json={"title": "Pack", "author": "mallory"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][0] == "save_policy_pack"
    assert api.calls[0][1]["author"] == "policy-admin"


def test_contract_negotiation_binds_missing_agent_to_principal():
    client, api = _mounted_client(
        {"actor": "agent-1", "capabilities": ["security:operate"]}
    )

    response = client.post(
        "/security/contracts/negotiate",
        json={"proposed_terms": []},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][1]["agent_id"] == "agent-1"


def test_contract_negotiation_rejects_cross_agent_identity():
    client, api = _mounted_client(
        {"actor": "agent-1", "capabilities": ["security:operate"]}
    )

    response = client.post(
        "/security/contracts/negotiate",
        json={"agent_id": "agent-2", "proposed_terms": []},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_admin_can_negotiate_for_explicit_agent():
    client, api = _mounted_client(
        {"actor": "admin", "capabilities": ["security:admin"]}
    )

    response = client.post(
        "/security/contracts/negotiate",
        json={"agent_id": "agent-2", "proposed_terms": []},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][1]["agent_id"] == "agent-2"


def test_contract_sign_rejects_cross_agent_signer():
    client, api = _mounted_client(
        {"actor": "agent-1", "capabilities": ["security:operate"]}
    )

    response = client.post(
        "/security/contracts/contract-1/sign",
        json={"signer_id": "agent-2", "algorithm": "hmac_sha256", "signature": "x"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_contract_detail_allows_contract_party():
    api = _RecordingAPI()
    api.broker.contracts["contract-1"] = _Contract(
        agent_id="agent-1",
        server_id="server-1",
    )
    client, api = _mounted_client({"actor": "agent-1"}, api=api)

    response = client.get(
        "/security/contracts/contract-1",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls == [("get_contract_details", {"contract_id": "contract-1"})]


def test_contract_detail_rejects_non_party():
    api = _RecordingAPI()
    api.broker.contracts["contract-1"] = _Contract(
        agent_id="agent-1",
        server_id="server-1",
    )
    client, api = _mounted_client({"actor": "agent-2"}, api=api)

    response = client.get(
        "/security/contracts/contract-1",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_exchange_log_static_route_enforces_session_ownership():
    api = _RecordingAPI()
    api.broker.sessions["session-1"] = _Session(
        agent_id="agent-1",
        server_id="server-1",
    )
    client, api = _mounted_client({"actor": "agent-1"}, api=api)

    response = client.get(
        "/security/contracts/exchange-log?session_id=session-1",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls == [("get_exchange_log_entries", {"session_id": "session-1"})]


def test_exchange_log_rejects_another_agents_session():
    api = _RecordingAPI()
    api.broker.sessions["session-1"] = _Session(
        agent_id="agent-1",
        server_id="server-1",
    )
    client, api = _mounted_client({"actor": "agent-2"}, api=api)

    response = client.get(
        "/security/contracts/exchange-log?session_id=session-1",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_contract_list_defaults_to_principal_identity():
    client, api = _mounted_client({"actor": "agent-1"})

    response = client.get("/security/contracts", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    assert api.calls[0][1]["agent_id"] == "agent-1"


def test_contract_list_rejects_cross_agent_query():
    client, api = _mounted_client({"actor": "agent-1"})

    response = client.get(
        "/security/contracts?agent_id=agent-2",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []


def test_consent_grant_uses_verified_principal_as_grantor():
    client, api = _mounted_client(
        {"actor": "consent-admin", "capabilities": ["security:admin"]}
    )

    response = client.post(
        "/security/consent/grant",
        json={"source_id": "resource", "target_id": "agent", "granted_by": "mallory"},
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert api.calls[0][1]["granted_by"] == "consent-admin"


def test_reflexive_read_rejects_cross_actor_query():
    client, api = _mounted_client({"actor": "agent-1"})

    response = client.get(
        "/security/reflexive/introspect/agent-2",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 403
    assert api.calls == []

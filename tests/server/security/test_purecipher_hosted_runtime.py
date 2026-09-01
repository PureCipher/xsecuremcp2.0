"""Regression tests for hosted OpenAPI execution boundaries."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from fastmcp.exceptions import ToolError
from fastmcp.server.security.policy.policies.allowlist import AllowlistPolicy
from purecipher import PureCipherRegistry
from purecipher.auth import RegistryAuthSettings, RegistryRole, RegistrySession
from purecipher.hosted_runtime import ToolsetGatewayRouter
from purecipher.openapi_gateway import (
    OpenAPIGateway,
    OpenAPIGatewayConfig,
    UnsafeOutboundHeaderError,
    _safe_request_headers,
    build_openapi_gateway_security,
)
from purecipher.outbound_security import (
    OutboundResponseTooLargeError,
    UnsafeOutboundPathError,
)


def _spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "paths": {
            "/users/{user_id}": {
                "get": {
                    "operationId": "lookupUser",
                    "summary": "Look up a user",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


class _Store:
    def __init__(self) -> None:
        self.toolset = {
            "toolset_id": "toolset-users",
            "source_id": "source-users",
            "selected_operations": ["lookupUser"],
            "tool_name_prefix": "directory",
            "metadata": {},
        }

    def get_toolset(self, toolset_id: str) -> dict[str, Any] | None:
        return self.toolset if toolset_id == "toolset-users" else None

    def get_source_spec(self, source_id: str) -> dict[str, Any] | None:
        return _spec() if source_id == "source-users" else None


def _gateway(
    monkeypatch: pytest.MonkeyPatch,
    client: httpx.AsyncClient,
    *,
    max_response_bytes: int = 4 * 1024 * 1024,
) -> OpenAPIGateway:
    store = _Store()
    monkeypatch.setattr(
        "purecipher.openapi_gateway.OpenAPIStore",
        lambda persistence_path: store,
    )
    return OpenAPIGateway(
        "hosted-users",
        config=OpenAPIGatewayConfig(
            toolset_id="toolset-users",
            persistence_path="unused",
            upstream_base_url="https://users.example/v1",
            max_response_bytes=max_response_bytes,
        ),
        http_client=client,
    )


async def test_hosted_gateway_encodes_path_segments_without_base_path_escape(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        gateway = _gateway(monkeypatch, client)
        await gateway.call_tool(
            "directory.lookupUser",
            {"payload": {"path": {"user_id": "abc/def"}}},
        )

    assert captured[0].url.raw_path == b"/v1/users/abc%2Fdef"
    context = gateway.security_context
    assert context is not None
    assert context.provenance_ledger is not None
    records = context.provenance_ledger.all_records
    assert records[-1].resource_id == "directory.lookupUser"


async def test_hosted_gateway_rejects_traversal_path_before_request(
    monkeypatch: pytest.MonkeyPatch,
):
    called = False

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        gateway = _gateway(monkeypatch, client)
        with pytest.raises(ToolError, match="dot segments") as exc_info:
            await gateway.call_tool(
                "directory.lookupUser",
                {"payload": {"path": {"user_id": "%2e%2e%2fadmin"}}},
                run_middleware=False,
            )

    assert isinstance(exc_info.value.__cause__, UnsafeOutboundPathError)
    assert called is False


@pytest.mark.parametrize(
    "name",
    [
        "Authorization",
        "Cookie",
        "Host",
        "Transfer-Encoding",
        "X-Forwarded-For",
        "X-Original-URL",
        "X-Real-IP",
    ],
)
def test_hosted_gateway_rejects_security_sensitive_caller_headers(name: str):
    with pytest.raises(UnsafeOutboundHeaderError, match=name):
        _safe_request_headers({name: "attacker-controlled"})


async def test_hosted_gateway_caps_upstream_response(
    monkeypatch: pytest.MonkeyPatch,
):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * 11)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = _gateway(monkeypatch, client, max_response_bytes=10)
        with pytest.raises(ToolError, match="10-byte limit") as exc_info:
            await gateway.call_tool(
                "directory.lookupUser",
                {"payload": {"path": {"user_id": "123"}}},
                run_middleware=False,
            )

    assert isinstance(exc_info.value.__cause__, OutboundResponseTooLargeError)


async def test_hosted_gateway_has_fail_closed_policy_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = _gateway(monkeypatch, client)

    context = gateway.security_context
    assert context is not None
    assert context.policy_engine is not None
    assert context.policy_engine.fail_closed is True
    allowlist = context.policy_engine.providers[0]
    assert isinstance(allowlist, AllowlistPolicy)
    assert allowlist.allowed == {"directory.lookupUser"}
    assert context.provenance_ledger is not None


def _auth_settings() -> RegistryAuthSettings:
    return RegistryAuthSettings.from_values(
        enabled=True,
        issuer="purecipher-registry",
        jwt_secret="hosted-runtime-session-secret-long-enough-for-sha256",
        cookie_secure=False,
        users_json=json.dumps(
            [
                {
                    "username": "viewer",
                    "password": "viewer-password",
                    "role": "viewer",
                    "display_name": "Registry Viewer",
                }
            ]
        ),
    )


def test_hosted_router_requires_revocation_aware_session_resolver():
    with pytest.raises(ValueError, match="revocation-aware"):
        ToolsetGatewayRouter(
            persistence_path="unused",
            auth_settings=_auth_settings(),
        )


def test_non_public_visibility_fails_closed_without_authentication():
    router = ToolsetGatewayRouter(persistence_path="unused")

    response = router._enforce_visibility(
        toolset={"metadata": {"hosting_visibility": "protected"}},
        scope={"headers": []},
    )

    assert response is not None
    assert response.status_code == 503


def test_private_visibility_requires_an_explicit_user_allowlist():
    settings = _auth_settings()
    session = RegistrySession(
        username="viewer",
        role=RegistryRole.VIEWER,
        display_name="Registry Viewer",
        expires_at="",
    )
    router = ToolsetGatewayRouter(
        persistence_path="unused",
        auth_settings=settings,
        session_resolver=lambda **tokens: session,
    )

    response = router._enforce_visibility(
        toolset={
            "metadata": {
                "hosting_visibility": "private",
                "allowed_users": [],
            }
        },
        scope={"headers": []},
    )

    assert response is not None
    assert response.status_code == 403


async def test_hosted_router_extracts_toolset_id_from_mounted_root_path(
    monkeypatch: pytest.MonkeyPatch,
):
    router = ToolsetGatewayRouter(persistence_path="unused")
    store = _Store()
    seen: list[str] = []

    async def app(scope, receive, send) -> None:
        return None

    async def ensure(toolset_id: str):
        seen.append(toolset_id)
        return app

    monkeypatch.setattr(router, "_store", store)
    monkeypatch.setattr(router, "_ensure_toolset_app", ensure)

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message) -> None:
        return None

    await router(
        {
            "type": "http",
            "path": "/mcp/toolsets/toolset-users",
            "root_path": "/mcp/toolsets",
            "headers": [],
        },
        receive,
        send,
    )

    assert seen == ["toolset-users"]


def test_hosted_router_rejects_revoked_registry_session():
    settings = _auth_settings()
    registry = PureCipherRegistry(
        signing_secret="hosted-runtime-signing-secret",
        auth_settings=settings,
        enable_contracts=False,
        enable_consent=False,
        enable_reflexive=False,
    )
    user = settings.users[0]
    record = registry._account_security.create_session(
        user=user,
        ttl_seconds=settings.token_ttl_seconds,
    )
    token = settings.issue_token(user, session_id=record.session_id)
    router = ToolsetGatewayRouter(
        persistence_path="unused",
        auth_settings=settings,
        session_resolver=registry.resolve_registry_session,
    )
    scope = {
        "headers": [
            (
                b"cookie",
                f"{settings.cookie_name}={token}".encode(),
            )
        ]
    }

    assert router._session_from_scope(scope) is not None
    registry._account_security.revoke_session(
        session_id=record.session_id,
        username=user.username,
    )
    assert router._session_from_scope(scope) is None

    issued = registry._account_security.create_api_token(
        username=user.username,
        name="Hosted runtime",
    )
    api_token_scope = {
        "headers": [(b"authorization", f"Bearer {issued['token']}".encode())]
    }
    assert router._session_from_scope(api_token_scope) is not None
    token_record = issued["token_record"]
    registry._account_security.revoke_api_token(
        username=user.username,
        token_id=str(token_record["token_id"]),
    )
    assert router._session_from_scope(api_token_scope) is None


def test_hosted_security_reuses_registry_audit_components():
    registry = PureCipherRegistry(
        signing_secret="hosted-runtime-shared-security-secret",
        enable_contracts=False,
        enable_consent=False,
        enable_reflexive=False,
    )
    shared_context = registry.security_context
    assert shared_context is not None
    config = build_openapi_gateway_security(
        _Store().toolset,
        shared_context=shared_context,
    )

    assert config.provenance is not None
    assert config.provenance.ledger is shared_context.provenance_ledger
    assert config.alerts is not None
    assert config.alerts.event_bus is shared_context.event_bus

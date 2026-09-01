"""Security regressions for remote OPA policy evaluation."""

from __future__ import annotations

import json
from typing import Any

import pytest

from fastmcp.server.security.outbound import OutboundHTTPResponse
from fastmcp.server.security.policy.policies import rego as rego_module
from fastmcp.server.security.policy.policies.rego import OPAHttpRegoPolicy
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)


def _context() -> PolicyEvaluationContext:
    return PolicyEvaluationContext(
        actor_id="agent-1",
        action="call_tool",
        resource_id="weather",
        resource_type="tool",
    )


def test_opa_production_transport_uses_hardened_request_boundary(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    def send(url: str, **kwargs: Any) -> OutboundHTTPResponse:
        captured["url"] = url
        captured.update(kwargs)
        return OutboundHTTPResponse(
            status_code=200,
            headers={},
            content=json.dumps({"result": {"allow": True}}).encode(),
        )

    monkeypatch.setattr(rego_module, "secure_outbound_request", send)
    policy = OPAHttpRegoPolicy(
        base_url="https://opa.example",
        package_path="securemcp.capability",
    )

    result = policy.evaluate(_context())

    assert result.decision is PolicyDecision.ALLOW
    assert captured["url"] == ("https://opa.example/v1/data/securemcp/capability")
    assert captured["method"] == "POST"
    assert captured["max_response_bytes"] == 1024 * 1024


def test_opa_default_policy_fails_closed_for_local_cleartext_target():
    policy = OPAHttpRegoPolicy(
        base_url="http://127.0.0.1:8181",
        package_path="securemcp/capability",
    )

    result = policy.evaluate(_context())

    assert result.decision is PolicyDecision.DENY
    assert "fail-closed" in result.reason
    assert "HTTPS" in result.reason


@pytest.mark.parametrize(
    "payload",
    [
        {"result": []},
        {"result": {"allow": 1}},
        {"result": {"allow": True, "deny": "not-a-list"}},
        ["not-an-object"],
    ],
)
def test_opa_malformed_responses_fail_closed(payload: Any):
    policy = OPAHttpRegoPolicy(
        base_url="https://opa.example",
        package_path="securemcp/capability",
        transport=lambda _url, _body: payload,
    )

    result = policy.evaluate(_context())

    assert result.decision is PolicyDecision.DENY


@pytest.mark.parametrize(
    "package_path",
    ["", "../secrets", "safe/../../secrets", "safe?query=x", "safe#fragment"],
)
def test_opa_package_path_rejects_non_package_segments(package_path: str):
    with pytest.raises(ValueError, match="plain Rego package segments"):
        OPAHttpRegoPolicy(
            base_url="https://opa.example",
            package_path=package_path,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "file:///etc/passwd",
        "https://user:secret@opa.example",
        "https://opa.example?target=other",
        "https://opa.example#fragment",
    ],
)
def test_opa_base_url_rejects_ambiguous_or_credentialed_urls(base_url: str):
    with pytest.raises(ValueError, match="base_url"):
        OPAHttpRegoPolicy(
            base_url=base_url,
            package_path="securemcp/capability",
        )


def test_opa_invalid_json_response_fails_closed(monkeypatch: pytest.MonkeyPatch):
    def send(_url: str, **_kwargs: Any) -> OutboundHTTPResponse:
        return OutboundHTTPResponse(
            status_code=200,
            headers={},
            content=b"not-json",
        )

    monkeypatch.setattr(rego_module, "secure_outbound_request", send)
    policy = OPAHttpRegoPolicy(
        base_url="https://opa.example",
        package_path="securemcp/capability",
    )

    result = policy.evaluate(_context())

    assert result.decision is PolicyDecision.DENY
    assert "valid JSON" in result.reason

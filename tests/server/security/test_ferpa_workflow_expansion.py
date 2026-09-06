"""Server-side evidence hook; institutional workflows are deliberately external."""

from dataclasses import replace
from typing import Any

import pytest

from fastmcp.server.security.middleware.policy_enforcement import (
    PolicyEnforcementMiddleware,
)
from fastmcp.server.security.policy.engine import PolicyEngine
from tests.server.security.test_ferpa_pack_boundaries import policy, request


@pytest.mark.anyio
async def test_resolver_supplies_trusted_context_and_rechecks_each_request():
    bound = request()
    calls = []

    async def resolve(context):
        calls.append(context)
        return bound.ferpa_evidence if len(calls) == 1 else None

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[policy()]), ferpa_evidence_resolver=resolve
    )
    plain = replace(bound, ferpa_evidence=None)
    assert (await middleware._evaluate(plain)).decision.value == "allow"
    assert (await middleware._evaluate(plain)).decision.value == "deny"
    assert len(calls) == 2


@pytest.mark.anyio
async def test_resolver_outage_denies():
    async def resolve(context):
        raise RuntimeError("unavailable")

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[policy()]), ferpa_evidence_resolver=resolve
    )
    assert (await middleware._evaluate(request())).decision.value == "deny"


@pytest.mark.anyio
async def test_evidence_time_is_evaluated_after_resolver_returns():
    from datetime import datetime, timedelta, timezone

    bound = request()

    async def resolve(context):
        now = datetime.now(timezone.utc)
        return replace(
            bound.ferpa_evidence,
            verified_at=now,
            expires_at=now + timedelta(seconds=30),
        )

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[policy()]), ferpa_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(bound, ferpa_evidence=None))
    ).decision.value == "allow"


@pytest.mark.anyio
async def test_prompt_arguments_are_bound_to_evidence():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from fastmcp.server.security.policy.provider import PolicyDecision, PolicyResult

    middleware = PolicyEnforcementMiddleware(PolicyEngine(providers=[policy()]))
    middleware._build_context = Mock(return_value=request())
    middleware._evaluate = AsyncMock(
        return_value=PolicyResult(
            decision=PolicyDecision.ALLOW, reason="fixture", policy_id="fixture"
        )
    )
    context: Any = SimpleNamespace(
        message=SimpleNamespace(name="student-summary", arguments={"student": "s1"}),
        fastmcp_context=object(),
    )
    await middleware.on_get_prompt(context, AsyncMock())
    assert middleware._build_context.call_args.kwargs["extra_metadata"] == {
        "arguments": {"student": "s1"}
    }

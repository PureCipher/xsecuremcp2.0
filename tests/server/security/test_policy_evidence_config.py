from dataclasses import fields, replace
from typing import Any

import pytest

from fastmcp.server.security.config import (
    PolicyConfig,
    PolicyEvidenceResolvers,
    SecurityConfig,
)
from fastmcp.server.security.middleware.policy_enforcement import (
    PolicyEnforcementMiddleware,
)
from fastmcp.server.security.orchestrator import SecurityOrchestrator
from tests.server.security.test_strict_change_policy import fixture


@pytest.mark.parametrize("name", [f.name for f in fields(PolicyEvidenceResolvers)])
def test_every_resolver_reaches_standard_middleware(name):
    async def resolve(context):
        return None

    resolvers = PolicyEvidenceResolvers(**{name: resolve})
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(policy=PolicyConfig(evidence_resolvers=resolvers))
    )
    middleware = next(
        m for m in ctx.middleware if isinstance(m, PolicyEnforcementMiddleware)
    )
    assert getattr(middleware, name) is resolve


@pytest.mark.anyio
async def test_bootstrapped_change_evidence_enforces_request_and_outage():
    p, c = fixture()
    calls = 0

    async def resolve(context):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("authority unavailable")
        return c.change_evidence

    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(
            policy=PolicyConfig(
                providers=[p],
                evidence_resolvers=PolicyEvidenceResolvers(
                    change_evidence_resolver=resolve
                ),
            )
        )
    )
    middleware = next(
        m for m in ctx.middleware if isinstance(m, PolicyEnforcementMiddleware)
    )
    request = replace(c, change_evidence=None)
    assert (await middleware._evaluate(request)).decision.value == "allow"
    assert (await middleware._evaluate(request)).decision.value == "deny"
    ctx = SecurityOrchestrator.bootstrap(
        SecurityConfig(policy=PolicyConfig(providers=[p]))
    )
    middleware = next(
        m for m in ctx.middleware if isinstance(m, PolicyEnforcementMiddleware)
    )
    assert (await middleware._evaluate(request)).decision.value == "deny"


def test_config_rejects_metadata_as_resolver():
    malformed: Any = {"approved": True}
    with pytest.raises(TypeError, match="must be a callable"):
        PolicyEvidenceResolvers(change_evidence_resolver=malformed)

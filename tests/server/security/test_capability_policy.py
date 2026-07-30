"""Tests for the SecureMCP capability policy layer.

Covers the Rego + Cedar default bundle and the decision-chain
extension that turned the Policy Kernel into a capability-based
authorizer. Each test reflects a line item from the original brief.

The tests deliberately go through the :class:`PolicyEngine` rather
than calling providers directly whenever possible — the engine's
aggregation rules (DENY short-circuits, REQUIRE_APPROVAL beats
ALLOW) are part of the contract and need to be exercised.
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.policy.audit import PolicyAuditLog
from fastmcp.server.security.policy.capability import (
    DEFAULT_CEDAR_POLICY,
    DEFAULT_REGO_MODULE,
    default_capability_bundle,
)
from fastmcp.server.security.policy.engine import (
    PolicyEngine,
    PolicyViolationError,
)
from fastmcp.server.security.policy.policies.cedar import (
    CedarParseError,
    CedarPolicy,
)
from fastmcp.server.security.policy.policies.rego import (
    OPAHttpRegoPolicy,
    RegoParseError,
    RegoPolicy,
)
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)

# ── Helpers ────────────────────────────────────────────────────────


def _ctx(
    *,
    action: str = "call_tool",
    resource_id: str = "hello",
    resource_type: str = "tool",
    environment: str = "production",
    principal_type: str = "agent",
    risk: str = "low",
    approval_granted: bool = False,
    approval_ticket: str | None = None,
    tags: frozenset[str] | None = None,
    actor_id: str = "agent-1",
) -> PolicyEvaluationContext:
    """Shorthand for building an evaluation context in a test.

    Kept verbose on purpose so each test's intent is legible without
    reaching for the dataclass definition.
    """
    return PolicyEvaluationContext(
        actor_id=actor_id,
        action=action,
        resource_id=resource_id,
        resource_type=resource_type,
        principal_type=principal_type,
        environment=environment,
        risk=risk,
        approval_granted=approval_granted,
        approval_ticket=approval_ticket,
        tags=tags or frozenset(),
    )


async def _engine_decision(ctx: PolicyEvaluationContext) -> PolicyDecision:
    engine = PolicyEngine(providers=default_capability_bundle())
    result = await engine.evaluate(ctx)
    return result.decision


# ── Requirement 3: backup deletion is ALWAYS blocked ───────────────


class TestBackupsAlwaysDeny:
    """The brief calls out backup deletion as a hard floor — no
    approval, no environment override, no curator-side exception
    should ever let it through.
    """

    @pytest.mark.parametrize(
        "environment,approval_granted,action,resource_type",
        [
            ("production", False, "delete", "backup"),
            ("production", True, "delete", "backup"),
            ("staging", True, "destroy", "backup"),
            ("development", True, "purge", "backup"),
            ("production", True, "rm", "backup"),
            ("production", True, "delete_backup", "tool"),
        ],
    )
    async def test_backup_destructive_is_always_denied(
        self,
        environment: str,
        approval_granted: bool,
        action: str,
        resource_type: str,
    ):
        ctx = _ctx(
            action=action,
            resource_id="nightly-backup",
            resource_type=resource_type,
            environment=environment,
            approval_granted=approval_granted,
            approval_ticket="tkt-override" if approval_granted else None,
        )
        assert await _engine_decision(ctx) == PolicyDecision.DENY


# ── Requirement 2 + 4: destructive prod actions require approval ───


class TestDestructiveProductionActionsRequireApproval:
    """Destructive actions against sensitive resource categories in
    production must not auto-execute — they may be allowed only with
    an explicit approval ticket.

    This is the central ask of the brief. Parametrized across every
    category the brief enumerates so a regression in any single one
    fails loud.
    """

    # Maps the brief's action groups to the labels the Rego/Cedar
    # bundle encodes against. Keep this table aligned with the
    # resource_type list in capability/bundle.py.
    SENSITIVE_RESOURCES = [
        "database",
        "cluster",
        "iam_role",
        "cloud_resource",
        "deployment",
        "dns_record",
        "firewall_rule",
        "credential",
        "secret",
    ]

    @pytest.mark.parametrize("resource_type", SENSITIVE_RESOURCES)
    async def test_destructive_prod_action_requires_approval(self, resource_type: str):
        ctx = _ctx(
            action="delete",
            resource_id=f"prod-{resource_type}-1",
            resource_type=resource_type,
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    @pytest.mark.parametrize("resource_type", SENSITIVE_RESOURCES)
    async def test_destructive_prod_action_with_approval_is_allowed(
        self, resource_type: str
    ):
        ctx = _ctx(
            action="delete",
            resource_id=f"prod-{resource_type}-1",
            resource_type=resource_type,
            environment="production",
            approval_granted=True,
            approval_ticket="ticket-123",
        )
        assert await _engine_decision(ctx) == PolicyDecision.ALLOW

    async def test_k8s_cluster_rollback_requires_approval(self):
        # Extra scenario from the brief: "Kubernetes changes". We
        # model a cluster as resource_type="cluster".
        ctx = _ctx(
            action="rollback",
            resource_id="prod-cluster-a",
            resource_type="cluster",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    async def test_dns_record_update_requires_approval(self):
        ctx = _ctx(
            action="update",
            resource_id="mx-record",
            resource_type="dns_record",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    async def test_firewall_rule_change_requires_approval(self):
        ctx = _ctx(
            action="create",
            resource_id="fw-allow-8080",
            resource_type="firewall_rule",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    async def test_credential_rotate_requires_approval(self):
        ctx = _ctx(
            action="rotate",
            resource_id="service-account-token",
            resource_type="credential",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL


# ── Requirement 5: production is read-only for agents by default ───


class TestProductionAgentsAreReadOnly:
    """Agents in production may read freely but any write/mutation
    must climb the approval stairway. The default bundle relaxes this
    only when an approval_ticket is present on the evaluation context.
    """

    async def test_prod_agent_read_resource_allowed(self):
        ctx = _ctx(
            action="read_resource",
            resource_id="prod-metrics-report",
            resource_type="resource",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.ALLOW

    async def test_prod_agent_call_benign_tool_allowed(self):
        ctx = _ctx(
            action="call_tool",
            resource_id="hello_world",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.ALLOW

    async def test_prod_agent_write_requires_approval(self):
        ctx = _ctx(
            action="write",
            resource_id="prod-orders-queue",
            resource_type="tool",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    async def test_prod_agent_write_with_approval_is_allowed(self):
        ctx = _ctx(
            action="write",
            resource_id="prod-orders-queue",
            resource_type="tool",
            environment="production",
            approval_granted=True,
            approval_ticket="tkt-555",
        )
        assert await _engine_decision(ctx) == PolicyDecision.ALLOW


# ── Requirement 1: deny-by-default when nothing matches ────────────


class TestDenyByDefault:
    """A call that doesn't match any explicit permit must not slip
    through. The engine's ``fail_closed`` default carries this for us
    once the bundle stops returning ALLOW for unknown cases.
    """

    async def test_empty_providers_fail_closed(self):
        engine = PolicyEngine(providers=[], fail_closed=True)
        decision = (await engine.evaluate(_ctx())).decision
        assert decision == PolicyDecision.DENY

    async def test_bundle_plus_unknown_resource_in_prod_returns_require_approval(
        self,
    ):
        # An unknown resource_type + write action in prod hits the
        # "production agent writes require approval" rule rather
        # than an unexplained ALLOW.
        ctx = _ctx(
            action="update",
            resource_id="unknown-thing",
            resource_type="widget",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL


# ── Engine decision aggregation (REQUIRE_APPROVAL + DENY + ALLOW) ──


class TestDecisionAggregation:
    """Validates the engine's new precedence rules: DENY overrides
    REQUIRE_APPROVAL overrides ALLOW.
    """

    async def test_deny_beats_require_approval(self):
        # Cedar's backup forbid short-circuits DENY even though the
        # Rego bundle would otherwise escalate to REQUIRE_APPROVAL
        # for a production write.
        ctx = _ctx(
            action="delete",
            resource_id="nightly-backup",
            resource_type="backup",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.DENY

    async def test_require_approval_beats_allow(self):
        # Prod DB update: Rego says REQUIRE_APPROVAL, the bundle's
        # allow-with-approval branch doesn't fire without a ticket.
        # The engine must surface REQUIRE_APPROVAL, not ALLOW.
        ctx = _ctx(
            action="update",
            resource_id="orders-db",
            resource_type="database",
            environment="production",
            approval_granted=False,
        )
        assert await _engine_decision(ctx) == PolicyDecision.REQUIRE_APPROVAL

    async def test_approval_ticket_resolves_to_allow(self):
        ctx = _ctx(
            action="update",
            resource_id="orders-db",
            resource_type="database",
            environment="production",
            approval_granted=True,
            approval_ticket="tkt-approve-9999",
        )
        assert await _engine_decision(ctx) == PolicyDecision.ALLOW


# ── Requirement 8: audit log captures the full six-tuple ───────────


class TestAuditCoverage:
    """Every evaluation records actor/action/resource/environment/
    risk/approval_status alongside the decision and reason. This is
    how the operator proves the kernel saw the call.
    """

    async def test_audit_records_capability_fields(self):
        audit = PolicyAuditLog()
        engine = PolicyEngine(
            providers=default_capability_bundle(),
            audit_log=audit,
        )
        await engine.evaluate(
            _ctx(
                action="update",
                resource_id="prod-db",
                resource_type="database",
                environment="production",
                risk="high",
                approval_granted=False,
                actor_id="agent-under-test",
            )
        )
        entries = audit.query(limit=1)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.actor_id == "agent-under-test"
        assert entry.action == "update"
        assert entry.resource_id == "prod-db"
        assert entry.environment == "production"
        assert entry.risk == "high"
        assert entry.principal_type == "agent"
        assert entry.resource_type == "database"
        assert entry.approval_granted is False
        assert entry.decision == PolicyDecision.REQUIRE_APPROVAL

    async def test_audit_records_approval_ticket(self):
        audit = PolicyAuditLog()
        engine = PolicyEngine(
            providers=default_capability_bundle(),
            audit_log=audit,
        )
        await engine.evaluate(
            _ctx(
                action="update",
                resource_id="prod-db",
                resource_type="database",
                environment="production",
                approval_granted=True,
                approval_ticket="tkt-1",
            )
        )
        entry = audit.query(limit=1)[0]
        assert entry.approval_granted is True
        assert entry.approval_ticket == "tkt-1"


# ── Provider-level tests: parse errors + edge cases ────────────────


class TestRegoEvaluator:
    def test_default_bundle_parses(self):
        RegoPolicy(DEFAULT_REGO_MODULE)

    def test_malformed_policy_raises(self):
        # Dangling operator — the evaluator must fail at load, not at
        # eval, so operators learn about typos at deploy time.
        with pytest.raises(RegoParseError):
            RegoPolicy(
                """
                package test
                deny[msg] {
                    input.action ==
                }
                """
            )

    async def test_allow_then_deny_short_circuits(self):
        # Hand-rolled policy: deny beats allow even though allow also
        # fires. Mirrors the engine-level contract at the provider
        # layer.
        source = """
        package t
        default allow = false
        allow {
            input.environment == "staging"
        }
        deny[msg] {
            input.environment == "staging"
            msg := "staging is locked down this weekend"
        }
        """
        p = RegoPolicy(source, policy_id="custom-rego")
        result = p.evaluate(_ctx(environment="staging"))
        assert result.decision == PolicyDecision.DENY
        assert "locked down" in result.reason


class TestCedarEvaluator:
    def test_default_bundle_parses(self):
        CedarPolicy(DEFAULT_CEDAR_POLICY)

    def test_malformed_policy_raises(self):
        with pytest.raises(CedarParseError):
            CedarPolicy("permit ( ;")

    async def test_forbid_beats_permit(self):
        source = """
        permit (principal, action, resource);
        forbid (principal, action, resource)
            when { context.environment == "production" };
        """
        p = CedarPolicy(source, policy_id="custom-cedar")
        assert (
            p.evaluate(_ctx(environment="production")).decision == PolicyDecision.DENY
        )
        assert p.evaluate(_ctx(environment="staging")).decision == PolicyDecision.ALLOW

    async def test_annotation_promotes_to_require_approval(self):
        source = """
        permit (
            principal,
            action == Action::"delete",
            resource
        )
        // @require_approval
        ;
        """
        p = CedarPolicy(source)
        ctx = _ctx(action="delete", approval_granted=False)
        assert p.evaluate(ctx).decision == PolicyDecision.REQUIRE_APPROVAL

    async def test_annotation_consumed_by_approval_ticket(self):
        source = """
        permit (
            principal,
            action == Action::"delete",
            resource
        )
        // @require_approval
        ;
        """
        p = CedarPolicy(source)
        ctx = _ctx(
            action="delete",
            approval_granted=True,
            approval_ticket="tkt-ok",
        )
        assert p.evaluate(ctx).decision == PolicyDecision.ALLOW


class TestOPAHttpAdapter:
    """The OPA HTTP adapter is exercised with an injected transport so
    the test suite never reaches the network. The adapter's contract
    is: translate the context to ``input``, read ``allow`` / ``deny``
    / ``require_approval`` out of the response, fail-closed on error.
    """

    async def test_allow_from_opa_response(self):
        calls: list[tuple[str, dict]] = []

        def fake_transport(url: str, body: dict) -> dict:
            calls.append((url, body))
            return {"result": {"allow": True}}

        p = OPAHttpRegoPolicy(
            base_url="http://opa.local",
            package_path="securemcp/capability",
            transport=fake_transport,
        )
        result = p.evaluate(_ctx())
        assert result.decision == PolicyDecision.ALLOW
        # URL sanity + input plumbing.
        assert calls[0][0] == "http://opa.local/v1/data/securemcp/capability"
        assert calls[0][1]["input"]["environment"] == "production"

    async def test_deny_wins_over_allow(self):
        def fake_transport(url: str, body: dict) -> dict:
            return {
                "result": {
                    "allow": True,
                    "deny": ["prod write without approval"],
                }
            }

        p = OPAHttpRegoPolicy(
            base_url="http://opa.local",
            package_path="x/y",
            transport=fake_transport,
        )
        result = p.evaluate(_ctx())
        assert result.decision == PolicyDecision.DENY
        assert "prod write without approval" in result.reason

    async def test_require_approval_demoted_by_ticket(self):
        def fake_transport(url: str, body: dict) -> dict:
            return {
                "result": {
                    "allow": True,
                    "require_approval": ["needs human"],
                }
            }

        p = OPAHttpRegoPolicy(
            base_url="http://opa.local",
            package_path="x/y",
            transport=fake_transport,
        )
        result_no_approval = p.evaluate(_ctx(approval_granted=False))
        assert result_no_approval.decision == PolicyDecision.REQUIRE_APPROVAL

        result_with_approval = p.evaluate(
            _ctx(approval_granted=True, approval_ticket="tkt")
        )
        assert result_with_approval.decision == PolicyDecision.ALLOW

    async def test_transport_error_fail_closes(self):
        def fake_transport(url: str, body: dict) -> dict:
            raise RuntimeError("opa outage")

        p = OPAHttpRegoPolicy(
            base_url="http://opa.local",
            package_path="x/y",
            transport=fake_transport,
        )
        result = p.evaluate(_ctx())
        assert result.decision == PolicyDecision.DENY
        assert "fail-closed" in result.reason.lower()


# ── Middleware-level: REQUIRE_APPROVAL surfaces as a violation ─────


class TestMiddlewareBehavior:
    """Sanity-check that the middleware treats REQUIRE_APPROVAL as a
    blocking decision. The middleware wraps both DENY and
    REQUIRE_APPROVAL in :class:`PolicyViolationError` so the downstream
    caller sees a consistent error shape.
    """

    async def test_policy_violation_error_carries_decision(self):
        from fastmcp.server.security.policy.provider import PolicyResult

        result = PolicyResult(
            decision=PolicyDecision.REQUIRE_APPROVAL,
            reason="Production DB update requires approval",
            policy_id="capability-bundle-rego",
        )
        err = PolicyViolationError(result)
        assert err.result.decision == PolicyDecision.REQUIRE_APPROVAL
        # The stringified error exposes both the id and the reason so
        # operators reading a client's MCP error response can trace it
        # back to the policy without an audit-log lookup.
        assert "capability-bundle-rego" in str(err)
        assert "approval" in str(err).lower()

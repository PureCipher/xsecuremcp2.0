"""Tests for Consent Graph data models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastmcp.server.security.consent.models import (
    ConsentCondition,
    ConsentDecision,
    ConsentEdge,
    ConsentNode,
    ConsentQuery,
    ConsentScope,
    ConsentStatus,
    NodeType,
)


class TestConsentNode:
    def test_default_node(self):
        node = ConsentNode()
        assert node.node_id == ""
        assert node.node_type == NodeType.AGENT

    def test_node_with_values(self):
        node = ConsentNode(
            node_id="agent-1",
            node_type=NodeType.RESOURCE,
            label="My Resource",
        )
        assert node.node_id == "agent-1"
        assert node.node_type == NodeType.RESOURCE

    def test_node_frozen(self):
        node = ConsentNode(node_id="test")
        try:
            node.node_id = "changed"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestConsentEdge:
    def test_default_edge(self):
        edge = ConsentEdge()
        assert edge.status == ConsentStatus.ACTIVE
        assert edge.delegatable is False
        assert edge.delegation_depth == 0

    def test_edge_is_valid(self):
        edge = ConsentEdge(status=ConsentStatus.ACTIVE)
        assert edge.is_valid()

    def test_edge_not_valid_when_revoked(self):
        edge = ConsentEdge(status=ConsentStatus.REVOKED)
        assert not edge.is_valid()

    def test_edge_not_valid_when_expired(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        edge = ConsentEdge(expires_at=past)
        assert not edge.is_valid()

    def test_edge_valid_before_expiry(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        edge = ConsentEdge(expires_at=future)
        assert edge.is_valid()

    def test_can_delegate_false_by_default(self):
        edge = ConsentEdge()
        assert not edge.can_delegate()

    def test_can_delegate_when_enabled(self):
        edge = ConsentEdge(delegatable=True)
        assert edge.can_delegate()

    def test_can_delegate_respects_depth(self):
        edge = ConsentEdge(
            delegatable=True,
            max_delegation_depth=2,
            delegation_depth=2,
        )
        assert not edge.can_delegate()

    def test_can_delegate_within_depth(self):
        edge = ConsentEdge(
            delegatable=True,
            max_delegation_depth=3,
            delegation_depth=1,
        )
        assert edge.can_delegate()

    def test_unique_edge_ids(self):
        e1 = ConsentEdge()
        e2 = ConsentEdge()
        assert e1.edge_id != e2.edge_id


class TestConsentCondition:
    def test_empty_expression_always_true(self):
        cond = ConsentCondition()
        assert cond.evaluate({})

    def test_simple_expression(self):
        cond = ConsentCondition(expression="role == 'admin'")
        assert cond.evaluate({"role": "admin"})
        assert not cond.evaluate({"role": "user"})

    def test_expression_with_len(self):
        cond = ConsentCondition(expression="len(items) > 0")
        assert cond.evaluate({"items": [1, 2, 3]})
        assert not cond.evaluate({"items": []})

    def test_invalid_expression_returns_false(self):
        cond = ConsentCondition(expression="invalid syntax !!!")
        assert not cond.evaluate({})

    def test_missing_variable_returns_false(self):
        cond = ConsentCondition(expression="missing_var > 5")
        assert not cond.evaluate({})

    def test_check_conditions_on_edge(self):
        cond = ConsentCondition(expression="time_of_day == 'business_hours'")
        edge = ConsentEdge(conditions=[cond])
        assert edge.check_conditions({"time_of_day": "business_hours"})
        assert not edge.check_conditions({"time_of_day": "night"})

    def test_multiple_conditions_all_must_pass(self):
        c1 = ConsentCondition(expression="role == 'admin'")
        c2 = ConsentCondition(expression="region == 'US'")
        edge = ConsentEdge(conditions=[c1, c2])
        assert edge.check_conditions({"role": "admin", "region": "US"})
        assert not edge.check_conditions({"role": "admin", "region": "EU"})


class TestConsentQuery:
    def test_default_query(self):
        q = ConsentQuery()
        assert q.source_id == ""
        assert q.scope == ""
        assert q.allow_delegation is True


class TestConsentDecision:
    def test_default_denied(self):
        d = ConsentDecision()
        assert not d.granted
        assert d.path == []


class TestConsentScopes:
    def test_scope_values(self):
        assert ConsentScope.READ.value == "read"
        assert ConsentScope.WRITE.value == "write"
        assert ConsentScope.EXECUTE.value == "execute"
        assert ConsentScope.LIST.value == "list"
        assert ConsentScope.ADMIN.value == "admin"
        assert ConsentScope.DELEGATE.value == "delegate"

"""Regression tests for the ``read_only`` policy constraint.

The earlier implementation logged ``read_only`` constraints but allowed
the tool call to proceed. This test set locks in the new behaviour: the
constraint actually blocks tool execution unless the tool itself
declares it is read-only via tags.
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.middleware.policy_enforcement import (
    PolicyEnforcementMiddleware,
    _tool_is_readonly,
)
from fastmcp.server.security.policy.engine import (
    PolicyEngine,
    PolicyViolationError,
)
from fastmcp.server.security.policy.provider import AllowAllPolicy


class _FakeMessage:
    def __init__(self, name: str = "tool", arguments: dict | None = None) -> None:
        self.name = name
        self.arguments = arguments or {}


class _FakeContext:
    """Minimal MiddlewareContext stand-in for constraint testing."""

    def __init__(self, name: str = "tool", arguments: dict | None = None) -> None:
        self.message = _FakeMessage(name, arguments)


class TestReadOnlyTagDetection:
    def test_empty_tags(self):
        assert _tool_is_readonly(frozenset()) is False

    def test_unrelated_tags(self):
        assert _tool_is_readonly(frozenset({"experimental", "alpha"})) is False

    def test_canonical_tag(self):
        assert _tool_is_readonly(frozenset({"read_only"})) is True

    def test_alias_tags(self):
        assert _tool_is_readonly(frozenset({"readonly"})) is True
        assert _tool_is_readonly(frozenset({"safe"})) is True

    def test_case_insensitive(self):
        assert _tool_is_readonly(frozenset({"READ_ONLY"})) is True
        assert _tool_is_readonly(frozenset({"Safe"})) is True


class TestReadOnlyConstraintEnforcement:
    """Regression tests: the read_only policy constraint must actually
    block tool calls, not merely log them."""

    def _make_middleware(self) -> PolicyEnforcementMiddleware:
        return PolicyEnforcementMiddleware(
            policy_engine=PolicyEngine(providers=[AllowAllPolicy()])
        )

    def test_read_only_blocks_unmarked_tool(self):
        mw = self._make_middleware()
        ctx = _FakeContext(name="write_data")
        with pytest.raises(PolicyViolationError) as exc_info:
            mw._enforce_constraints(
                constraints=["read_only"],
                resource_id="write_data",
                context=ctx,
                tool_tags=frozenset(),
            )
        assert "read_only" in str(exc_info.value).lower()
        assert "write_data" in str(exc_info.value)

    def test_read_only_allows_tagged_tool(self):
        mw = self._make_middleware()
        ctx = _FakeContext(name="get_status")
        # No exception means the constraint was satisfied.
        mw._enforce_constraints(
            constraints=["read_only"],
            resource_id="get_status",
            context=ctx,
            tool_tags=frozenset({"read_only"}),
        )

    def test_read_only_allows_safe_tag(self):
        mw = self._make_middleware()
        ctx = _FakeContext(name="ping")
        mw._enforce_constraints(
            constraints=["read_only"],
            resource_id="ping",
            context=ctx,
            tool_tags=frozenset({"safe"}),
        )

    def test_read_only_allows_readonly_alias(self):
        mw = self._make_middleware()
        ctx = _FakeContext(name="describe")
        mw._enforce_constraints(
            constraints=["read_only"],
            resource_id="describe",
            context=ctx,
            tool_tags=frozenset({"readonly"}),
        )

    def test_read_only_blocks_when_unrelated_tags_present(self):
        """Having other tags doesn't satisfy the constraint."""
        mw = self._make_middleware()
        ctx = _FakeContext(name="delete_user")
        with pytest.raises(PolicyViolationError):
            mw._enforce_constraints(
                constraints=["read_only"],
                resource_id="delete_user",
                context=ctx,
                tool_tags=frozenset({"experimental", "admin"}),
            )

    def test_read_only_combines_with_other_constraints(self):
        """A blocked read_only must take precedence even when other
        constraints would have passed."""
        mw = self._make_middleware()
        ctx = _FakeContext(name="write_thing", arguments={"a": 1})
        with pytest.raises(PolicyViolationError) as exc_info:
            mw._enforce_constraints(
                constraints=["max_args:5", "read_only", "log_access"],
                resource_id="write_thing",
                context=ctx,
                tool_tags=frozenset(),
            )
        assert "read_only" in str(exc_info.value).lower()

    def test_max_args_still_enforced(self):
        """Sanity check: existing constraint enforcement still works
        end-to-end, since this fix touched the same method."""
        mw = self._make_middleware()
        ctx = _FakeContext(name="tool", arguments={"a": 1, "b": 2, "c": 3})
        with pytest.raises(PolicyViolationError) as exc_info:
            mw._enforce_constraints(
                constraints=["max_args:2"],
                resource_id="tool",
                context=ctx,
                tool_tags=frozenset(),
            )
        assert "max_args" in str(exc_info.value)

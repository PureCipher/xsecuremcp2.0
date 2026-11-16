"""Regression coverage for parsed email-recipient domain restrictions."""

from __future__ import annotations

from typing import Any

import pytest

from fastmcp import Client
from fastmcp.server.security.config import PolicyConfig, SecurityConfig
from fastmcp.server.security.policy import EmailRecipientDomainPolicy
from fastmcp.server.security.policy.declarative import dump_policy_schema, load_policy
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)
from fastmcp.server.security.policy.serialization import (
    policy_provider_from_config,
    policy_provider_to_config,
)
from securemcp import SecureMCP


def _policy(**overrides: Any) -> EmailRecipientDomainPolicy:
    values: dict[str, Any] = {
        "allowed_domains": {"acme.com"},
        "tool_patterns": {"send_email"},
        "argument_paths": ("to", "cc", "bcc"),
    }
    values.update(overrides)
    return EmailRecipientDomainPolicy(**values)


def _context(
    arguments,
    *,
    resource_id: str = "send_email",
    action: str = "call_tool",
    method: str | None = "tools/call",
) -> PolicyEvaluationContext:
    metadata = {"arguments": arguments}
    if method is not None:
        metadata["method"] = method
    return PolicyEvaluationContext(
        actor_id="registered-client",
        action=action,
        resource_id=resource_id,
        metadata=metadata,
    )


@pytest.mark.parametrize(
    "recipients",
    [
        "bob@acme.com",
        "Bob Example <bob@ACME.COM>",
        "bob+alerts@acme.com, alice@acme.com",
        ["bob@acme.com", "Alice Example <alice@acme.com>"],
    ],
)
async def test_all_parsed_allowed_recipients_are_accepted(recipients):
    result = await _policy().evaluate(_context({"to": recipients}))

    assert result.decision is PolicyDecision.ALLOW


async def test_mixed_recipient_string_is_denied_even_when_final_address_is_allowed():
    result = await _policy().evaluate(_context({"to": "x@evil.net, bob@acme.com"}))

    assert result.decision is PolicyDecision.DENY
    assert "evil.net" in result.reason
    assert "bob@acme.com" not in result.reason


@pytest.mark.parametrize(
    "recipient",
    [
        "x@evil.net; bob@acme.com",
        "x@evil.net bob@acme.com",
        "x@evil.net Bcc: bob@acme.com",
        "x@evil.net\r\nBcc: bob@acme.com",
        "Undisclosed recipients:;",
        "bob@acme.com (outside@evil.net)",
        '"x@evil.net, bob"@acme.com',
        '"Evil, Corp" <bob@acme.com>',
        "bob@acme.com,",
        ",bob@acme.com",
        "not-an-address",
        "",
    ],
)
async def test_ambiguous_or_header_like_recipient_values_fail_closed(recipient):
    result = await _policy().evaluate(_context({"to": recipient}))

    assert result.decision is PolicyDecision.DENY
    assert "recipient" in result.reason.lower()


async def test_every_nested_recipient_argument_is_checked():
    policy = _policy(argument_paths=("content.to", "content.cc", "content.bcc"))
    result = await policy.evaluate(
        _context(
            {
                "content": {
                    "to": ["owner@acme.com"],
                    "cc": [],
                    "bcc": ["hidden@evil.net"],
                }
            }
        )
    )

    assert result.decision is PolicyDecision.DENY
    assert "evil.net" in result.reason


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"to": None},
        {"to": []},
        {"to": ["bob@acme.com", 7]},
        {"to": {"address": "bob@acme.com"}},
    ],
)
async def test_missing_empty_or_wrongly_typed_recipients_fail_closed(arguments):
    result = await _policy().evaluate(_context(arguments))

    assert result.decision is PolicyDecision.DENY


async def test_empty_optional_recipient_paths_do_not_override_valid_to_address():
    result = await _policy().evaluate(
        _context({"to": ["bob@acme.com"], "cc": [], "bcc": None})
    )

    assert result.decision is PolicyDecision.ALLOW


async def test_nonmatching_tools_and_non_call_operations_are_unaffected():
    policy = _policy(tool_patterns={"mail_*"})

    other_tool = await policy.evaluate(_context({}, resource_id="calculator"))
    list_call = await policy.evaluate(
        _context({}, resource_id="mail_send", action="list_tools", method=None)
    )

    assert other_tool.decision is PolicyDecision.ALLOW
    assert list_call.decision is PolicyDecision.ALLOW


async def test_subdomains_require_explicit_opt_in_and_use_label_boundaries():
    strict = _policy()
    permissive = _policy(allow_subdomains=True)

    assert (
        await strict.evaluate(_context({"to": "bob@team.acme.com"}))
    ).decision is PolicyDecision.DENY
    assert (
        await permissive.evaluate(_context({"to": "bob@team.acme.com"}))
    ).decision is PolicyDecision.ALLOW
    assert (
        await permissive.evaluate(_context({"to": "bob@evilacme.com"}))
    ).decision is PolicyDecision.DENY


async def test_recipient_count_limit_is_fail_closed():
    policy = _policy(max_recipients=2)

    result = await policy.evaluate(
        _context({"to": "one@acme.com, two@acme.com, three@acme.com"})
    )

    assert result.decision is PolicyDecision.DENY


async def test_policy_can_allow_no_recipients_when_explicitly_configured():
    result = await _policy(require_recipient=False).evaluate(_context({}))

    assert result.decision is PolicyDecision.ALLOW


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"allowed_domains": set()}, "allowed_domains"),
        ({"allowed_domains": {"@acme.com"}}, "Invalid email domain"),
        ({"allowed_domains": {"acme.com.evil..net"}}, "Invalid email domain"),
        ({"tool_patterns": set()}, "tool_patterns"),
        ({"argument_paths": ("content..to",)}, "argument_paths"),
        ({"argument_paths": ("to", " to ")}, "argument_paths"),
        ({"max_recipients": 0}, "max_recipients"),
        ({"max_recipients": True}, "max_recipients"),
    ],
)
def test_invalid_policy_configuration_is_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        _policy(**overrides)


def test_declarative_policy_and_version_snapshot_round_trip():
    config = {
        "type": "email_recipient_domains",
        "policy_id": "internal-mail",
        "version": "2.0.0",
        "allowed_domains": ["acme.com", "example.org"],
        "tool_patterns": ["send_email", "gmail_send_*"],
        "argument_paths": ["to", "content.to", "content.cc"],
        "allow_subdomains": True,
        "require_recipient": True,
        "max_recipients": 25,
    }

    loaded = load_policy(config)
    serialized = policy_provider_to_config(loaded)
    restored = policy_provider_from_config(serialized)

    assert isinstance(loaded, EmailRecipientDomainPolicy)
    assert isinstance(restored, EmailRecipientDomainPolicy)
    assert serialized == {**config, "tool_patterns": sorted(config["tool_patterns"])}
    assert restored.allowed_domains == {"acme.com", "example.org"}
    assert restored.argument_paths == ("to", "content.to", "content.cc")


def test_declarative_schema_exposes_safe_starter_configuration():
    descriptor = dump_policy_schema()["policy_types"]["email_recipient_domains"]

    assert descriptor["category"] == "data_control"
    assert descriptor["field_specs"]["allowed_domains"]["required"] is True
    assert descriptor["field_specs"]["argument_paths"]["required"] is True
    assert descriptor["starter_config"]["type"] == "email_recipient_domains"


async def test_end_to_end_mixed_recipient_call_never_executes_tool():
    delivered: list[str] = []
    server = SecureMCP(
        "recipient-policy-regression",
        security=SecurityConfig(policy=PolicyConfig(providers=[_policy()])),
    )

    @server.tool
    def send_email(to: str, body: str) -> str:
        del body
        delivered.extend(address.strip() for address in to.split(","))
        return "sent"

    async with Client(server) as client:
        result = await client.call_tool(
            "send_email",
            {"to": "x@evil.net, bob@acme.com", "body": "Q3 figures"},
            raise_on_error=False,
        )

    assert result.is_error
    assert delivered == []
    assert "Recipient domain is not allowed" in str(result.content)


async def test_end_to_end_allowed_recipients_execute_normally():
    delivered: list[str] = []
    server = SecureMCP(
        "recipient-policy-allowed",
        security=SecurityConfig(policy=PolicyConfig(providers=[_policy()])),
    )

    @server.tool
    def send_email(to: str, body: str) -> str:
        del body
        delivered.extend(address.strip() for address in to.split(","))
        return "sent"

    async with Client(server) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "send_email",
            {"to": "alice@acme.com, bob@acme.com", "body": "Q3 figures"},
            raise_on_error=False,
        )

    assert [tool.name for tool in tools] == ["send_email"]
    assert not result.is_error
    assert delivered == ["alice@acme.com", "bob@acme.com"]

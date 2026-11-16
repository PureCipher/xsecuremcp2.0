"""Fail-closed email recipient domain policy.

This policy parses complete mailbox lists before checking domains. It avoids
suffix checks such as ``value.endswith("@example.com")``, which can approve a
mixed recipient string when only its final address belongs to the allowed
domain.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from email.headerregistry import Address
from typing import Any

from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

_DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_MAX_RECIPIENTS_LIMIT = 1_000
_MAX_ARGUMENT_VALUE_LENGTH = 8_192


class RecipientAddressError(ValueError):
    """Raised internally when a recipient value cannot be parsed safely."""


def _normalize_domain(value: str) -> str:
    """Return a canonical ASCII DNS domain or raise ``ValueError``."""

    if not isinstance(value, str):
        raise ValueError("Email domains must be strings")
    candidate = value.strip().rstrip(".")
    if not candidate or candidate.startswith("@") or len(candidate) > 253:
        raise ValueError(f"Invalid email domain: {value!r}")
    try:
        normalized = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError(f"Invalid email domain: {value!r}") from None
    labels = normalized.split(".")
    if any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise ValueError(f"Invalid email domain: {value!r}")
    return normalized


def _argument_value(arguments: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a dotted path without interpreting user-controlled objects."""

    current: Any = arguments
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _extract_addr_spec(segment: str) -> str:
    """Extract one conservative addr-spec without version-specific parsers."""

    candidate = segment.strip()
    if not candidate or any(character in candidate for character in ";:()"):
        raise RecipientAddressError("Recipient value is malformed")

    if "<" not in candidate and ">" not in candidate:
        return candidate
    if (
        candidate.count("<") != 1
        or candidate.count(">") != 1
        or not candidate.endswith(">")
    ):
        raise RecipientAddressError("Recipient value is malformed")
    display_name, addr_spec = candidate[:-1].split("<", 1)
    if any(character in display_name for character in "<>") or not addr_spec.strip():
        raise RecipientAddressError("Recipient value is malformed")
    return addr_spec.strip()


def _parse_recipient_value(value: Any, *, remaining: int) -> list[str]:
    """Parse a string or string list into normalized recipient domains."""

    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list | tuple):
        if len(value) > remaining:
            raise RecipientAddressError("Recipient count exceeds the policy limit")
        raw_values = value
    else:
        raise RecipientAddressError("Recipient values must be strings or lists")

    domains: list[str] = []
    for raw in raw_values:
        if (
            not isinstance(raw, str)
            or not raw.strip()
            or len(raw) > _MAX_ARGUMENT_VALUE_LENGTH
            or _has_control_characters(raw)
        ):
            raise RecipientAddressError("Recipient value is malformed")
        # Parse every comma-delimited segment independently. This deliberately
        # rejects quoted commas: otherwise a strict RFC parser could see one
        # mailbox while a downstream mailer using ``split(",")`` sees two.
        for segment in raw.split(","):
            try:
                addr_spec = _extract_addr_spec(segment)
                mailbox = Address(addr_spec=addr_spec)
                if not mailbox.username or not mailbox.domain:
                    raise ValueError
                domain = _normalize_domain(mailbox.domain)
            except (IndexError, TypeError, ValueError):
                raise RecipientAddressError("Recipient value is malformed") from None
            domains.append(domain)
            if len(domains) > remaining:
                raise RecipientAddressError("Recipient count exceeds the policy limit")
    return domains


@dataclass
class EmailRecipientDomainPolicy:
    """Restrict parsed email recipients to approved DNS domains.

    ``tool_patterns`` scopes the policy to selected MCP tools. For matching tool
    calls, every mailbox found at ``argument_paths`` is parsed and checked. A
    dotted path such as ``"content.to"`` addresses nested argument objects.
    Missing or malformed recipient data fails closed when ``require_recipient``
    is true (the default).
    """

    allowed_domains: set[str]
    tool_patterns: set[str]
    argument_paths: tuple[str, ...] = ("to",)
    allow_subdomains: bool = False
    require_recipient: bool = True
    max_recipients: int = 100
    policy_id: str = "email-recipient-domain-policy"
    version: str = "1.0.0"
    _normalized_domains: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.allowed_domains, str) or not self.allowed_domains:
            raise ValueError("allowed_domains must contain at least one domain")
        if isinstance(self.tool_patterns, str) or not self.tool_patterns:
            raise ValueError("tool_patterns must contain at least one tool pattern")
        if isinstance(self.argument_paths, str) or not self.argument_paths:
            raise ValueError("argument_paths must contain at least one dotted path")
        if any(
            not isinstance(pattern, str) or not pattern.strip()
            for pattern in self.tool_patterns
        ):
            raise ValueError("tool_patterns must contain nonempty strings")
        if any(
            not isinstance(path, str)
            or not path.strip()
            or any(
                not segment or segment != segment.strip()
                for segment in path.strip().split(".")
            )
            for path in self.argument_paths
        ):
            raise ValueError("argument_paths must contain valid dotted paths")
        normalized_paths = tuple(path.strip() for path in self.argument_paths)
        if len(set(normalized_paths)) != len(normalized_paths):
            raise ValueError("argument_paths must not contain duplicates")
        if type(self.allow_subdomains) is not bool:
            raise ValueError("allow_subdomains must be a boolean")
        if type(self.require_recipient) is not bool:
            raise ValueError("require_recipient must be a boolean")
        if (
            type(self.max_recipients) is not int
            or self.max_recipients < 1
            or self.max_recipients > _MAX_RECIPIENTS_LIMIT
        ):
            raise ValueError(
                f"max_recipients must be between 1 and {_MAX_RECIPIENTS_LIMIT}"
            )

        normalized = frozenset(
            _normalize_domain(domain) for domain in self.allowed_domains
        )
        self.allowed_domains = set(normalized)
        self.tool_patterns = {pattern.strip() for pattern in self.tool_patterns}
        self.argument_paths = normalized_paths
        self._normalized_domains = normalized

    def _applies(self, context: PolicyEvaluationContext) -> bool:
        method = context.metadata.get("method")
        is_tool_call = (
            method == "tools/call"
            if method is not None
            else context.action == "call_tool"
        )
        return is_tool_call and any(
            fnmatch.fnmatchcase(context.resource_id, pattern)
            for pattern in self.tool_patterns
        )

    def _domain_allowed(self, domain: str) -> bool:
        for allowed in self._normalized_domains:
            if domain == allowed:
                return True
            if self.allow_subdomains and domain.endswith(f".{allowed}"):
                return True
        return False

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        """Parse and authorize all recipients for matching tool calls."""

        if not self._applies(context):
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="Email recipient domain policy does not apply",
                policy_id=self.policy_id,
            )

        arguments = context.metadata.get("arguments")
        if not isinstance(arguments, dict):
            return self._deny("Recipient arguments are missing or malformed")

        recipient_domains: list[str] = []
        try:
            for path in self.argument_paths:
                found, value = _argument_value(arguments, path)
                if not found or value is None or value == "" or value == []:
                    continue
                remaining = self.max_recipients - len(recipient_domains)
                recipient_domains.extend(
                    _parse_recipient_value(value, remaining=remaining)
                )
        except RecipientAddressError:
            return self._deny("Recipient arguments are missing or malformed")

        if not recipient_domains:
            if self.require_recipient:
                return self._deny("At least one valid email recipient is required")
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="No recipients were supplied and recipients are optional",
                policy_id=self.policy_id,
            )

        denied_domains = sorted(
            {domain for domain in recipient_domains if not self._domain_allowed(domain)}
        )
        if denied_domains:
            return self._deny(
                "Recipient domain is not allowed: " + ", ".join(denied_domains)
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=(
                f"All {len(recipient_domains)} parsed email recipient(s) use "
                "allowed domains"
            ),
            policy_id=self.policy_id,
        )

    def _deny(self, reason: str) -> PolicyResult:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason=reason,
            policy_id=self.policy_id,
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version


__all__ = ["EmailRecipientDomainPolicy"]

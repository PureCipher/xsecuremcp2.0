"""Capability authorization helpers for the SecureMCP HTTP API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

from starlette.requests import Request


class SecurityCapability(str, Enum):
    """Capabilities understood by the built-in HTTP authorizer."""

    READ = "security:read"
    OPERATE = "security:operate"
    ADMIN = "security:admin"


SecurityAuthorizer = Callable[
    [Request, dict[str, Any], SecurityCapability], Awaitable[bool] | bool
]
"""Callable that authorizes a verified principal for a route capability."""


_CAPABILITY_CLAIMS = ("capabilities", "permissions", "scopes", "scope", "scp")
_ACTOR_CLAIMS = ("sub", "actor", "id", "client_id")


def principal_actor(principal: dict[str, Any]) -> str | None:
    """Return the principal's stable actor identifier, if present."""
    for claim in _ACTOR_CLAIMS:
        value = principal.get(claim)
        if type(value) is str and value.strip():
            return value.strip()
    return None


def request_principal(request: Request) -> dict[str, Any] | None:
    """Return the verified principal stored on a request."""
    principal = getattr(request.state, "security_principal", None)
    return principal if type(principal) is dict else None


def request_principal_actor(request: Request) -> str | None:
    """Return the stable actor identifier for a request's principal."""
    principal = request_principal(request)
    return principal_actor(principal) if principal is not None else None


def principal_capabilities(
    principal: dict[str, Any],
) -> frozenset[SecurityCapability]:
    """Normalize supported OAuth/JWT capability claims.

    Principals without any capability claim retain read-only access for
    compatibility. Supplying an explicit but empty or invalid claim grants
    nothing.
    """
    claim_present = False
    tokens: set[str] = set()
    for claim in _CAPABILITY_CLAIMS:
        if claim not in principal:
            continue
        claim_present = True
        tokens.update(_capability_tokens(principal[claim]))

    if not claim_present:
        return frozenset({SecurityCapability.READ})

    return frozenset(
        capability for capability in SecurityCapability if capability.value in tokens
    )


def principal_has_capability(
    principal: dict[str, Any],
    required: SecurityCapability,
) -> bool:
    """Check a capability using the built-in hierarchy."""
    granted = principal_capabilities(principal)
    if SecurityCapability.ADMIN in granted:
        return True
    if required is SecurityCapability.READ and SecurityCapability.OPERATE in granted:
        return True
    return required in granted


def request_principal_is_admin(request: Request) -> bool:
    """Return whether a request carries the built-in administrator capability."""
    principal = request_principal(request)
    if principal is None:
        return False
    return principal_has_capability(principal, SecurityCapability.ADMIN)


def _capability_tokens(value: Any) -> set[str]:
    if type(value) is str:
        return set(value.split())
    if type(value) not in {list, tuple, set, frozenset}:
        return set()

    tokens: set[str] = set()
    for item in value:
        if type(item) is str:
            tokens.update(item.split())
    return tokens


__all__ = [
    "SecurityAuthorizer",
    "SecurityCapability",
    "principal_actor",
    "principal_capabilities",
    "principal_has_capability",
    "request_principal",
    "request_principal_actor",
    "request_principal_is_admin",
]

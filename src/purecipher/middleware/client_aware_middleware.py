"""SecureMCP middleware subclasses that read PureCipher's resolved
client slug as ``actor_id`` when one is available.

The four SecureMCP middlewares (policy / contract / consent /
provenance / reflexive) each independently extract ``actor_id``
from ``fastmcp.server.dependencies.get_access_token()`` and
truncate the token to an opaque 8-char prefix. That extraction
predates PureCipher's MCP-client identity model and is
unaware of our opaque API tokens.

These thin subclasses override the actor-extraction step on each
upstream middleware to *prefer* the contextvar-resolved client
slug populated by :class:`purecipher.middleware.client_actor
.ClientActorResolverMiddleware`. When the resolver populated a
slug, downstream evaluators see it as the actor; when no client
token was presented, the original SecureMCP behavior applies
unchanged.

Why subclass rather than fork the upstream files: every
SecureMCP middleware exposes the actor extraction through a
single hook (``_get_actor_id`` / ``_build_context``). Subclassing
keeps PureCipher's integration confined to a small adapter that
upstream maintainers can ignore — and SecureMCP can evolve
without breaking us.

The orchestrator wires the upstream middlewares; we replace each
instance in :class:`PureCipherRegistry`'s context with our
matching subclass after construction.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.security.middleware.consent_enforcement import (
    ConsentEnforcementMiddleware,
)
from fastmcp.server.security.middleware.contract_validation import (
    ContractValidationMiddleware,
)
from fastmcp.server.security.middleware.policy_enforcement import (
    PolicyEnforcementMiddleware,
)
from fastmcp.server.security.middleware.provenance_recording import (
    ProvenanceRecordingMiddleware,
)
from fastmcp.server.security.middleware.reflexive import ReflexiveMiddleware
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from purecipher.middleware.client_actor import current_client_actor

# ── Policy ─────────────────────────────────────────────────────────


class ClientAwarePolicyEnforcementMiddleware(PolicyEnforcementMiddleware):
    """``PolicyEnforcementMiddleware`` that prefers the resolved
    client slug as ``actor_id`` over the access-token prefix.

    The upstream middleware builds its
    :class:`PolicyEvaluationContext` inside ``_build_context``.
    We override that method, call the parent for everything else,
    then rewrite the resulting context with the resolved actor when
    one is present.
    """

    def _build_context(self, *args: Any, **kwargs: Any) -> PolicyEvaluationContext:
        ctx = super()._build_context(*args, **kwargs)
        actor = current_client_actor()
        if not actor:
            return ctx
        return PolicyEvaluationContext(
            actor_id=actor,
            action=ctx.action,
            resource_id=ctx.resource_id,
            metadata=ctx.metadata,
            timestamp=ctx.timestamp,
            tags=ctx.tags,
        )


# ── Contracts ──────────────────────────────────────────────────────


class ClientAwareContractValidationMiddleware(ContractValidationMiddleware):
    """``ContractValidationMiddleware`` whose
    ``_get_agent_id`` returns the resolved client slug when
    available.
    """

    def _get_agent_id(self, *args: Any, **kwargs: Any) -> str | None:
        actor = current_client_actor()
        if actor:
            return actor
        return super()._get_agent_id(*args, **kwargs)


# ── Consent ────────────────────────────────────────────────────────


class ClientAwareConsentEnforcementMiddleware(ConsentEnforcementMiddleware):
    """``ConsentEnforcementMiddleware`` whose actor extractor returns
    the resolved client slug when available.
    """

    def _get_actor_id(self, *args: Any, **kwargs: Any) -> str:
        actor = current_client_actor()
        if actor:
            return actor
        return super()._get_actor_id(*args, **kwargs)


# ── Provenance ─────────────────────────────────────────────────────


class ClientAwareProvenanceRecordingMiddleware(
    ProvenanceRecordingMiddleware
):
    """``ProvenanceRecordingMiddleware`` whose actor extractor
    returns the resolved client slug when available.
    """

    def _get_actor_id(self, *args: Any, **kwargs: Any) -> str:
        actor = current_client_actor()
        if actor:
            return actor
        return super()._get_actor_id(*args, **kwargs)


# ── Reflexive ──────────────────────────────────────────────────────


class ClientAwareReflexiveMiddleware(ReflexiveMiddleware):
    """``ReflexiveMiddleware`` whose actor extractor returns the
    resolved client slug when available.
    """

    def _get_actor_id(self, *args: Any, **kwargs: Any) -> str:
        actor = current_client_actor()
        if actor:
            return actor
        return super()._get_actor_id(*args, **kwargs)


# ── Map upstream → client-aware ───────────────────────────────────


_REPLACEMENT_MAP: list[tuple[type, type]] = [
    (PolicyEnforcementMiddleware, ClientAwarePolicyEnforcementMiddleware),
    (ContractValidationMiddleware, ClientAwareContractValidationMiddleware),
    (ConsentEnforcementMiddleware, ClientAwareConsentEnforcementMiddleware),
    (ProvenanceRecordingMiddleware, ClientAwareProvenanceRecordingMiddleware),
    (ReflexiveMiddleware, ClientAwareReflexiveMiddleware),
]


def upgrade_middleware_for_client_actor(middleware_chain: list) -> list:
    """Return a new chain where each upstream middleware is
    replaced with its client-aware subclass if one exists.

    Subclasses share the upstream class's ``__init__`` signature
    via ``__class__`` reassignment — we cast in place rather than
    re-construct, since each middleware holds references to
    plane-specific state (broker, ledger, etc.) we shouldn't
    rebuild.
    """
    upgraded: list = []
    for component in middleware_chain:
        replaced = False
        for upstream_cls, replacement_cls in _REPLACEMENT_MAP:
            if (
                isinstance(component, upstream_cls)
                and not isinstance(component, replacement_cls)
            ):
                # In-place class swap. The subclass is a structural
                # superset (no extra ``__init__``-only state) so
                # this is safe and avoids tearing down plane state.
                component.__class__ = replacement_cls
                replaced = True
                break
        upgraded.append(component)
        if not replaced:
            continue
    return upgraded


__all__ = [
    "ClientAwareConsentEnforcementMiddleware",
    "ClientAwareContractValidationMiddleware",
    "ClientAwarePolicyEnforcementMiddleware",
    "ClientAwareProvenanceRecordingMiddleware",
    "ClientAwareReflexiveMiddleware",
    "upgrade_middleware_for_client_actor",
]

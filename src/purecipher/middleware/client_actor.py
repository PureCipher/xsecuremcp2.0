"""Resolve MCP-client bearer tokens to a stable actor identity.

Iteration 10 lights up real client identities across every
SecureMCP control plane. The challenge: each downstream middleware
(policy / contract / consent / provenance / reflexive) builds its
``actor_id`` independently by reading
``fastmcp.server.dependencies.get_access_token()``. Unresolved opaque
tokens become token-derived pseudonymous principals — what we actually
want is the client's slug (``"claude-desktop"``, ``"acme-sales-bot"``,
etc.) so downstream telemetry filters consistently per client.

This module contributes two pieces:

1. :class:`ClientActorResolverMiddleware` — runs *first* in the
   security middleware chain. On each request:

   * Reads the ``Authorization: Bearer ...`` header.
   * Hands the token to the registry's
     :meth:`PureCipherRegistry.authenticate_client_token` method.
   * If valid and the client is active, stashes the resolved client's
     slug in a module-level :class:`~contextvars.ContextVar` for
     the duration of the call.
   * In strict mode, rejects missing, invalid, revoked, suspended, or
     otherwise unresolvable credentials before governance middleware can
     attach evidence to a pseudonymous principal.

2. :func:`current_client_actor` — small read accessor for that
   contextvar. The PureCipher-specific subclasses of the four
   downstream middlewares (see :mod:`purecipher.middleware
   .client_aware_middleware`) consult this first and fall back to
   the SecureMCP default extraction when no client token was
   presented.

Net effect: when a real MCP client sends a bearer token, every plane
sees the same stable ``actor_id`` (the client's slug). Development
deployments retain the permissive fallback unless strict mode is
requested; production registry deployments enable strict mode.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import AuthorizationError
from fastmcp.server.middleware.middleware import (
    CallNext,
    Middleware,
    MiddlewareContext,
)

if TYPE_CHECKING:
    from purecipher.registry import PureCipherRegistry

logger = logging.getLogger(__name__)


class ResolvedPrincipalRequiredError(AuthorizationError):
    """Raised when strict client-principal resolution cannot authenticate."""


_RESOLVED_PRINCIPAL_REQUIRED_MESSAGE = (
    "A valid registered client token is required for this MCP endpoint."
)


# Single global contextvar for the currently-resolving client.
# Each request sets it on entry and resets on exit; the helpers
# below provide read-only access for downstream middlewares.
_current_client_actor: ContextVar[str | None] = ContextVar(
    "purecipher_client_actor", default=None
)
_current_client_record: ContextVar[Any] = ContextVar(
    "purecipher_client_record", default=None
)


def current_client_actor() -> str | None:
    """Return the resolved client slug for the current call, or None.

    Used by the PureCipher-aware middleware subclasses and by the
    governance projection methods to consistently key telemetry
    per-client. Returns ``None`` when no client token was
    presented (or when the token didn't authenticate).
    """
    return _current_client_actor.get()


def current_client_record() -> Any:
    """Return the full :class:`RegistryClient` for the current call.

    Useful for tests + downstream consumers that need more than
    the slug (e.g. owner publisher, kind, status).
    """
    return _current_client_record.get()


class ClientActorResolverMiddleware(Middleware):
    """Resolves a bearer token to a registry client and exposes it
    via a contextvar for the duration of the call.

    The middleware runs first (inserted at index 0 of
    ``ctx.middleware`` by :class:`PureCipherRegistry`). It
    Development deployments may use it only as a resolver, preserving
    the framework's token-derived pseudonymous fallback. Strict deployments
    enforce resolved registry identity and reject the request before any
    downstream governance plane observes an unresolved actor.
    """

    def __init__(
        self,
        registry: PureCipherRegistry,
        *,
        require_resolved_principal: bool | None = None,
    ) -> None:
        self._registry = registry
        if require_resolved_principal is None:
            require_resolved_principal = registry.require_resolved_principal
        self._require_resolved_principal = bool(require_resolved_principal)

    @property
    def require_resolved_principal(self) -> bool:
        """Return whether unresolved client identity is rejected."""

        return self._require_resolved_principal

    async def __call__(
        self,
        context: MiddlewareContext,
        call_next: CallNext,
    ) -> Any:
        token_value = self._extract_bearer_token(context)
        token_actor: str | None = None
        token_record: Any = None
        resolution_failed = False
        if token_value:
            try:
                resolved = self._registry.authenticate_client_token(token_value)
            except Exception:
                logger.exception(
                    "Client principal resolution failed%s",
                    "; denying request" if self._require_resolved_principal else "",
                )
                resolved = None
                resolution_failed = True
            if resolved is not None:
                client, _ = resolved
                token_actor = client.slug
                token_record = client

        if token_actor is None and self._require_resolved_principal:
            if not resolution_failed:
                logger.warning(
                    "Denied MCP request without a resolved client principal "
                    "(method=%s, source=%s)",
                    context.method or "unknown",
                    context.source,
                )
            raise ResolvedPrincipalRequiredError(_RESOLVED_PRINCIPAL_REQUIRED_MESSAGE)

        actor_token = _current_client_actor.set(token_actor)
        record_token = _current_client_record.set(token_record)
        try:
            return await call_next(context)
        finally:
            _current_client_actor.reset(actor_token)
            _current_client_record.reset(record_token)

    @staticmethod
    def _extract_bearer_token(context: MiddlewareContext) -> str | None:
        """Pull the bearer secret out of the current HTTP request.

        Falls back to ``None`` when:

        * the request isn't an HTTP request (e.g. STDIO transport),
        * the header is missing,
        * the header value isn't ``Bearer ...``.

        Extraction itself never raises. The caller decides whether a missing
        token is allowed or rejected according to strict-mode configuration.
        """
        try:
            from fastmcp.server.dependencies import get_http_request

            request = get_http_request()
        except Exception:
            return None
        if request is None:
            return None
        auth = (
            request.headers.get("Authorization", "")
            if hasattr(request, "headers")
            else ""
        )
        if not auth or not auth.lower().startswith("bearer "):
            return None
        secret = auth[len("Bearer ") :].strip()
        return secret or None


__all__ = [
    "ClientActorResolverMiddleware",
    "ResolvedPrincipalRequiredError",
    "current_client_actor",
    "current_client_record",
]

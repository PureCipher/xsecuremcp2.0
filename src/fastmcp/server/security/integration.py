"""SecureMCP integration helpers for FastMCP servers.

These helpers keep SecureMCP wiring outside FastMCP core so security can be
attached through public server hooks instead of constructor patches.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from fastmcp.server.security.config import SecurityConfig
from fastmcp.server.security.orchestrator import SecurityContext, SecurityOrchestrator
from fastmcp.server.security.settings import SecuritySettings, get_security_settings
from fastmcp.tools.tool import Tool

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


_ATTACHED_SECURITY_CONTEXTS: WeakKeyDictionary[FastMCP, SecurityContext] = (
    WeakKeyDictionary()
)
_REGISTERED_GATEWAY_TOOLS: WeakKeyDictionary[FastMCP, set[str]] = WeakKeyDictionary()


def _apply_settings_overrides(
    config: SecurityConfig, settings: SecuritySettings
) -> SecurityConfig:
    """Return a copy of ``config`` with explicit env-var overrides applied.

    This honors ``SECUREMCP_POLICY_FAIL_CLOSED`` and
    ``SECUREMCP_POLICY_HOT_SWAP`` (and their ``FASTMCP_SECURITY_*``
    aliases) as ops-level overrides on whatever ``PolicyConfig`` the
    user supplied. The override only fires when the env var was
    *explicitly* set — fields left at their default values do not
    override the code-supplied PolicyConfig, so existing code-only
    deployments behave identically.
    """
    explicit_fields = settings.model_fields_set

    fail_closed_override = "policy_fail_closed" in explicit_fields
    hot_swap_override = "policy_hot_swap" in explicit_fields
    if not (fail_closed_override or hot_swap_override):
        return config

    policy = config.policy
    if policy is None:
        # No PolicyConfig means no policy layer is active; the env-var
        # override has nothing to bind to. Surface the disconnect so
        # operators see why their setting had no effect.
        logger.warning(
            "SECUREMCP_POLICY_* override(s) set but config.policy is None; "
            "the override has no effect. Provide a PolicyConfig() to enable "
            "policy enforcement."
        )
        return config

    new_policy_kwargs: dict = {}
    if fail_closed_override and policy.fail_closed != settings.policy_fail_closed:
        logger.info(
            "PolicyConfig.fail_closed overridden by SECUREMCP_POLICY_FAIL_CLOSED "
            "(was %s, now %s)",
            policy.fail_closed,
            settings.policy_fail_closed,
        )
        new_policy_kwargs["fail_closed"] = settings.policy_fail_closed
    if hot_swap_override and policy.allow_hot_swap != settings.policy_hot_swap:
        logger.info(
            "PolicyConfig.allow_hot_swap overridden by SECUREMCP_POLICY_HOT_SWAP "
            "(was %s, now %s)",
            policy.allow_hot_swap,
            settings.policy_hot_swap,
        )
        new_policy_kwargs["allow_hot_swap"] = settings.policy_hot_swap

    if not new_policy_kwargs:
        return config

    new_policy = replace(policy, **new_policy_kwargs)
    # If the engine was pre-built, replicate the override onto the live
    # engine instance so it actually takes effect at evaluation time.
    if new_policy.engine is not None:
        if "fail_closed" in new_policy_kwargs:
            new_policy.engine.fail_closed = new_policy_kwargs["fail_closed"]
        if "allow_hot_swap" in new_policy_kwargs:
            new_policy.engine.allow_hot_swap = new_policy_kwargs["allow_hot_swap"]

    return replace(config, policy=new_policy)


def get_security_context(server: FastMCP) -> SecurityContext | None:
    """Return the SecureMCP context for a server if one is attached."""

    return _ATTACHED_SECURITY_CONTEXTS.get(server)


def attach_security_context(
    server: FastMCP,
    context: SecurityContext,
    *,
    register_gateway_tools: bool = False,
) -> SecurityContext:
    """Attach an existing SecurityContext to a FastMCP server.

    This attaches middleware through the server's public hook and records the
    context in an external registry, keeping SecureMCP state out of core-owned
    server fields.
    """

    existing = get_security_context(server)
    if existing is not None:
        raise RuntimeError(f"SecureMCP is already attached to server {server.name!r}")

    for middleware in context.middleware:
        server.add_middleware(middleware)

    _ATTACHED_SECURITY_CONTEXTS[server] = context

    if register_gateway_tools:
        register_security_gateway_tools(server, context=context)

    return context


def attach_security(
    server: FastMCP,
    config: SecurityConfig,
    *,
    bypass_stdio: bool | None = None,
    settings: SecuritySettings | None = None,
    register_gateway_tools: bool = False,
) -> SecurityContext:
    """Bootstrap SecureMCP from config and attach it to a FastMCP server.

    Settings precedence:
        1. Explicit kwargs (``bypass_stdio=...``) win over everything.
        2. Explicitly-set env vars (``SECUREMCP_*``) override the
           ``SecurityConfig`` fields they map to.
        3. Code-supplied ``SecurityConfig`` values are otherwise used as-is.
    """

    resolved_settings = settings or get_security_settings()
    settings_applied_config = _apply_settings_overrides(config, resolved_settings)
    effective_config = (
        settings_applied_config
        if resolved_settings.enabled
        else replace(settings_applied_config, enabled=False)
    )
    effective_bypass_stdio = (
        resolved_settings.policy_bypass_stdio if bypass_stdio is None else bypass_stdio
    )

    if effective_bypass_stdio and effective_config.is_policy_enabled():
        # Loud one-line warning at startup so operators don't discover
        # the bypass after a security incident. Logged once per attach.
        logger.warning(
            "SecureMCP attached with bypass_stdio=True: policy/contract/"
            "provenance/consent middleware will NOT run for STDIO transport. "
            "Set bypass_stdio=False or SECUREMCP_POLICY_BYPASS_STDIO=false to "
            "enforce on STDIO too."
        )

    context = SecurityOrchestrator.bootstrap(
        effective_config,
        server_name=server.name,
        bypass_stdio=effective_bypass_stdio,
    )
    return attach_security_context(
        server,
        context,
        register_gateway_tools=register_gateway_tools,
    )


def register_security_gateway_tools(
    server: FastMCP,
    *,
    context: SecurityContext | None = None,
) -> list[str]:
    """Register SecureMCP gateway tools on a FastMCP server.

    Gateway tools are registered explicitly so the extension remains additive
    and opt-in.
    """

    context = context or get_security_context(server)
    if context is None:
        raise RuntimeError(
            f"No SecureMCP context is attached to server {server.name!r}"
        )

    added = _REGISTERED_GATEWAY_TOOLS.get(server)
    if added is None:
        added = set()
        _REGISTERED_GATEWAY_TOOLS[server] = added
    registered_now: list[str] = []

    for name, fn in context.gateway_tools.items():
        if name in added:
            continue
        server.add_tool(Tool.from_function(fn, name=name))
        added.add(name)
        registered_now.append(name)

    return registered_now

"""Policy enforcement middleware for SecureMCP.

Intercepts all MCP operations and evaluates them against the configured
policy engine before allowing execution. Follows the same patterns as
AuthMiddleware: fail-closed, STDIO bypass, list filtering.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

import mcp.types as mt

from fastmcp.prompts.base import Prompt, PromptResult
from fastmcp.resources.base import Resource, ResourceResult
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.middleware.middleware import (
    CallNext,
    Middleware,
    MiddlewareContext,
)
from fastmcp.server.security.policy.engine import (
    PolicyDecision,
    PolicyEngine,
    PolicyViolationError,
)
from fastmcp.server.security.policy.policies.ccpa_request import CcpaEvidence
from fastmcp.server.security.policy.policies.ferpa_request import FerpaEvidence
from fastmcp.server.security.policy.policies.pci_request import PciEvidence
from fastmcp.server.security.policy.policies.zero_trust import ZeroTrustEvidence
from fastmcp.server.security.policy.provider import (
    PolicyEvaluationContext,
    PolicyResult,
)
from fastmcp.server.security.principal import principal_id_from_access_token
from fastmcp.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class PolicyEnforcementMiddleware(Middleware):
    """Middleware that enforces policy decisions on all MCP operations.

    Evaluates every tool call, resource read, and prompt render against
    the configured PolicyEngine. Also filters list responses to only
    include policy-permitted components.

    Follows the same security patterns as AuthMiddleware:
    - Fail-closed when context is missing
    - STDIO transport bypass (configurable)
    - AND logic across all policy providers

    Args:
        policy_engine: The engine to evaluate requests against.
        bypass_stdio: If True, skip policy checks for STDIO transport.
            Defaults to ``False`` — STDIO is a privileged execution
            surface and the middleware evaluates it just like HTTP.
            See ``v3-notes/mcp-stdio-hardening.md`` for the rationale.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine,
        *,
        bypass_stdio: bool = False,
        ccpa_evidence_resolver: Callable[
            [PolicyEvaluationContext], Awaitable[CcpaEvidence | None]
        ]
        | None = None,
        pci_evidence_resolver: Callable[
            [PolicyEvaluationContext], Awaitable[PciEvidence | None]
        ]
        | None = None,
        zero_trust_evidence_resolver: Callable[
            [PolicyEvaluationContext], Awaitable[ZeroTrustEvidence | None]
        ]
        | None = None,
        ferpa_evidence_resolver: Callable[
            [PolicyEvaluationContext], Awaitable[FerpaEvidence | None]
        ]
        | None = None,
    ) -> None:
        self.policy_engine = policy_engine
        self.bypass_stdio = bypass_stdio
        self.ferpa_evidence_resolver = ferpa_evidence_resolver
        self.zero_trust_evidence_resolver = zero_trust_evidence_resolver
        self.pci_evidence_resolver = pci_evidence_resolver
        self.ccpa_evidence_resolver = ccpa_evidence_resolver

    async def _evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        if self.ferpa_evidence_resolver is not None and not context.action.startswith(
            "list_"
        ):
            try:
                evidence = await self.ferpa_evidence_resolver(context)
            except Exception:
                logger.warning("FERPA evidence resolution failed; denying request")
                return _deny_result("FERPA evidence is unavailable")
            context = replace(
                context, ferpa_evidence=evidence, timestamp=datetime.now(timezone.utc)
            )
        if self.zero_trust_evidence_resolver is not None:
            try:
                zero_evidence = await self.zero_trust_evidence_resolver(context)
            except Exception:
                logger.warning("Zero Trust evidence resolution failed; denying request")
                return _deny_result("Zero Trust evidence is unavailable")
            context = replace(
                context,
                zero_trust_evidence=zero_evidence,
                timestamp=datetime.now(timezone.utc),
            )
        if self.pci_evidence_resolver is not None:
            try:
                pci_evidence = await self.pci_evidence_resolver(context)
            except Exception:
                logger.warning("PCI evidence resolution failed; denying request")
                return _deny_result("PCI evidence is unavailable")
            context = replace(
                context, pci_evidence=pci_evidence, timestamp=datetime.now(timezone.utc)
            )
        if self.ccpa_evidence_resolver is not None:
            try:
                ccpa_evidence = await self.ccpa_evidence_resolver(context)
            except Exception:
                logger.warning("CCPA evidence resolution failed; denying request")
                return _deny_result("CCPA evidence is unavailable")
            context = replace(
                context,
                ccpa_evidence=ccpa_evidence,
                timestamp=datetime.now(timezone.utc),
            )
        return await self.policy_engine.evaluate(context)

    def _should_bypass(self) -> bool:
        """Check if policy checks should be skipped for current transport."""
        if not self.bypass_stdio:
            return False
        from fastmcp.server.context import _current_transport

        return _current_transport.get() == "stdio"

    def _build_context(
        self,
        action: str,
        resource_id: str,
        middleware_context: MiddlewareContext[mt.CallToolRequestParams]
        | MiddlewareContext[mt.ReadResourceRequestParams]
        | MiddlewareContext[mt.GetPromptRequestParams],
        extra_metadata: dict | None = None,
    ) -> PolicyEvaluationContext:
        """Build a PolicyEvaluationContext from a MiddlewareContext."""
        actor_id: str | None = None
        tags: frozenset[str] = frozenset()

        # Try to extract actor from access token
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
        actor_id = principal_id_from_access_token(token)

        metadata: dict = extra_metadata or {}
        metadata["method"] = middleware_context.method
        metadata["source"] = middleware_context.source

        capability = _capability_overrides(tags, metadata)
        policy_action = cast(str, capability.pop("action", action))
        return PolicyEvaluationContext(
            actor_id=actor_id,
            action=policy_action,
            resource_id=resource_id,
            metadata=metadata,
            timestamp=middleware_context.timestamp,
            tags=tags,
            **cast(Any, capability),
        )

    def _build_list_context(
        self,
        action: str,
        resource_id: str,
        tags: frozenset[str],
    ) -> PolicyEvaluationContext:
        """Build a lightweight context for list-level filtering."""
        from fastmcp.server.dependencies import get_access_token

        actor_id = principal_id_from_access_token(get_access_token())
        capability = _capability_overrides(tags, {})
        policy_action = cast(str, capability.pop("action", action))
        return PolicyEvaluationContext(
            actor_id=actor_id,
            action=policy_action,
            resource_id=resource_id,
            tags=tags,
            **cast(Any, capability),
        )

    # ── Tool operations ──────────────────────────────────────────────

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Evaluate policy before tool execution."""
        if self._should_bypass():
            return await call_next(context)

        tool_name = context.message.name
        fastmcp_ctx = context.fastmcp_context

        if fastmcp_ctx is None:
            logger.warning(
                "PolicyEnforcement: context is None for tool '%s'. Denying access.",
                tool_name,
            )
            raise PolicyViolationError(
                _deny_result(
                    f"Policy check failed for tool '{tool_name}': missing context"
                )
            )

        eval_ctx = self._build_context(
            action="call_tool",
            resource_id=tool_name,
            middleware_context=context,
            extra_metadata={"arguments": context.message.arguments or {}},
        )

        # Get tool to access its tags. We rebuild the evaluation
        # context so the capability fields (environment / risk /
        # resource_type) reflect the tool's tags — not the generic
        # defaults the first _build_context call used.
        tool = await fastmcp_ctx.fastmcp.get_tool(tool_name)
        if tool is not None:
            tool_tags = frozenset(tool.tags)
            capability = _capability_overrides(tool_tags, eval_ctx.metadata)
            policy_action = cast(str, capability.pop("action", eval_ctx.action))
            eval_ctx = PolicyEvaluationContext(
                actor_id=eval_ctx.actor_id,
                action=policy_action,
                resource_id=eval_ctx.resource_id,
                metadata=eval_ctx.metadata,
                timestamp=eval_ctx.timestamp,
                tags=tool_tags,
                **cast(Any, capability),
            )

        result = await self._evaluate(eval_ctx)
        # REQUIRE_APPROVAL is a non-terminal deny from the caller's
        # perspective — the action cannot execute right now but may
        # be retried with approval metadata attached. We reuse the
        # DENY surfacing so clients see a consistent error shape;
        # PolicyViolationError carries the original decision for
        # callers that want to branch.
        if result.decision in (
            PolicyDecision.DENY,
            PolicyDecision.REQUIRE_APPROVAL,
        ):
            raise PolicyViolationError(result)

        # Enforce constraints from policy result
        if result.constraints:
            tool_tags = frozenset(tool.tags) if tool is not None else frozenset()
            self._enforce_constraints(
                result.constraints,
                tool_name,
                context,
                tool_tags=tool_tags,
            )

        return await call_next(context)

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        """Filter tools list based on policy."""
        tools = await call_next(context)

        if self._should_bypass():
            return tools

        permitted: list[Tool] = []
        for tool in tools:
            eval_ctx = self._build_list_context(
                action="list_tools",
                resource_id=tool.name,
                tags=frozenset(tool.tags),
            )
            try:
                result = await self._evaluate(eval_ctx)
                # Hide components that need approval too — listing
                # them would invite callers to attempt calls that
                # won't succeed without a human-in-the-loop ticket.
                if result.decision not in (
                    PolicyDecision.DENY,
                    PolicyDecision.REQUIRE_APPROVAL,
                ):
                    permitted.append(tool)
            except Exception:
                logger.debug(
                    "Policy evaluation failed for tool '%s' during listing; excluding",
                    tool.name,
                )

        return permitted

    # ── Resource operations ──────────────────────────────────────────

    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, ResourceResult],
    ) -> ResourceResult:
        """Evaluate policy before resource read."""
        if self._should_bypass():
            return await call_next(context)

        uri = str(context.message.uri)
        fastmcp_ctx = context.fastmcp_context

        if fastmcp_ctx is None:
            logger.warning(
                "PolicyEnforcement: context is None for resource '%s'. Denying access.",
                uri,
            )
            raise PolicyViolationError(
                _deny_result(
                    f"Policy check failed for resource '{uri}': missing context"
                )
            )

        eval_ctx = self._build_context(
            action="read_resource",
            resource_id=uri,
            middleware_context=context,
        )

        result = await self._evaluate(eval_ctx)
        # REQUIRE_APPROVAL is a non-terminal deny from the caller's
        # perspective — the action cannot execute right now but may
        # be retried with approval metadata attached. We reuse the
        # DENY surfacing so clients see a consistent error shape;
        # PolicyViolationError carries the original decision for
        # callers that want to branch.
        if result.decision in (
            PolicyDecision.DENY,
            PolicyDecision.REQUIRE_APPROVAL,
        ):
            raise PolicyViolationError(result)

        return await call_next(context)

    async def on_list_resources(
        self,
        context: MiddlewareContext[mt.ListResourcesRequest],
        call_next: CallNext[mt.ListResourcesRequest, Sequence[Resource]],
    ) -> Sequence[Resource]:
        """Filter resources list based on policy."""
        resources = await call_next(context)

        if self._should_bypass():
            return resources

        permitted: list[Resource] = []
        for resource in resources:
            eval_ctx = self._build_list_context(
                action="list_resources",
                resource_id=str(resource.uri),
                tags=frozenset(resource.tags),
            )
            try:
                result = await self._evaluate(eval_ctx)
                if result.decision not in (
                    PolicyDecision.DENY,
                    PolicyDecision.REQUIRE_APPROVAL,
                ):
                    permitted.append(resource)
            except Exception:
                logger.debug(
                    "Policy evaluation failed for resource '%s' during listing; excluding",
                    resource.uri,
                )

        return permitted

    async def on_list_resource_templates(
        self,
        context: MiddlewareContext[mt.ListResourceTemplatesRequest],
        call_next: CallNext[
            mt.ListResourceTemplatesRequest, Sequence[ResourceTemplate]
        ],
    ) -> Sequence[ResourceTemplate]:
        """Filter resource templates list based on policy."""
        templates = await call_next(context)

        if self._should_bypass():
            return templates

        permitted: list[ResourceTemplate] = []
        for template in templates:
            eval_ctx = self._build_list_context(
                action="list_resource_templates",
                resource_id=str(template.uri_template),
                tags=frozenset(template.tags),
            )
            try:
                result = await self._evaluate(eval_ctx)
                if result.decision not in (
                    PolicyDecision.DENY,
                    PolicyDecision.REQUIRE_APPROVAL,
                ):
                    permitted.append(template)
            except Exception:
                logger.debug(
                    "Policy evaluation failed for template '%s' during listing; excluding",
                    template.uri_template,
                )

        return permitted

    # ── Prompt operations ────────────────────────────────────────────

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, PromptResult],
    ) -> PromptResult:
        """Evaluate policy before prompt render."""
        if self._should_bypass():
            return await call_next(context)

        prompt_name = context.message.name
        fastmcp_ctx = context.fastmcp_context

        if fastmcp_ctx is None:
            logger.warning(
                "PolicyEnforcement: context is None for prompt '%s'. Denying access.",
                prompt_name,
            )
            raise PolicyViolationError(
                _deny_result(
                    f"Policy check failed for prompt '{prompt_name}': missing context"
                )
            )

        eval_ctx = self._build_context(
            action="get_prompt",
            resource_id=prompt_name,
            middleware_context=context,
            extra_metadata={"arguments": context.message.arguments or {}},
        )

        result = await self._evaluate(eval_ctx)
        # REQUIRE_APPROVAL is a non-terminal deny from the caller's
        # perspective — the action cannot execute right now but may
        # be retried with approval metadata attached. We reuse the
        # DENY surfacing so clients see a consistent error shape;
        # PolicyViolationError carries the original decision for
        # callers that want to branch.
        if result.decision in (
            PolicyDecision.DENY,
            PolicyDecision.REQUIRE_APPROVAL,
        ):
            raise PolicyViolationError(result)

        return await call_next(context)

    async def on_list_prompts(
        self,
        context: MiddlewareContext[mt.ListPromptsRequest],
        call_next: CallNext[mt.ListPromptsRequest, Sequence[Prompt]],
    ) -> Sequence[Prompt]:
        """Filter prompts list based on policy."""
        prompts = await call_next(context)

        if self._should_bypass():
            return prompts

        permitted: list[Prompt] = []
        for prompt in prompts:
            eval_ctx = self._build_list_context(
                action="list_prompts",
                resource_id=prompt.name,
                tags=frozenset(prompt.tags),
            )
            try:
                result = await self._evaluate(eval_ctx)
                if result.decision not in (
                    PolicyDecision.DENY,
                    PolicyDecision.REQUIRE_APPROVAL,
                ):
                    permitted.append(prompt)
            except Exception:
                logger.debug(
                    "Policy evaluation failed for prompt '%s' during listing; excluding",
                    prompt.name,
                )

        return permitted

    def _enforce_constraints(
        self,
        constraints: list[str],
        resource_id: str,
        context: Any,
        *,
        tool_tags: frozenset[str] = frozenset(),
    ) -> None:
        """Enforce policy constraints.

        Constraints are strings that describe conditions that must be met.
        Known constraint types:

        - ``read_only``: The resource can only be read, not modified.
        - ``max_args:N``: Maximum number of arguments for tool calls.
        - ``require_metadata:KEY``: A metadata key must be present.
        - ``log_access``: Access must be logged (handled by audit log).

        Unknown constraints are logged as warnings but don't block execution.

        Args:
            constraints: List of constraint strings from PolicyResult.
            resource_id: The resource being accessed.
            context: The middleware context.
        """
        for constraint in constraints:
            constraint_lower = constraint.lower().strip()

            if constraint_lower == "read_only":
                # ``read_only`` means: this caller may only invoke tools
                # that the server has declared to be side-effect-free.
                # The declaration is made via the tool's tags — any of
                # ``read_only``, ``readonly``, or ``safe`` qualifies a
                # tool as read-only. Tool authors who actually mutate
                # state must NOT carry these tags; doing so is a server
                # operator's mis-tagging that the engine cannot detect.
                if _tool_is_readonly(tool_tags):
                    logger.debug(
                        "Constraint 'read_only' satisfied for %s (tool tags: %s)",
                        resource_id,
                        sorted(tool_tags),
                    )
                else:
                    raise PolicyViolationError(
                        _deny_result(
                            f"Constraint violation: read_only sessions cannot "
                            f"invoke '{resource_id}' (tool not tagged as "
                            f"read-only). Tag the tool with 'read_only' "
                            f"if it has no side effects."
                        )
                    )
                continue

            if constraint_lower.startswith("max_args:"):
                try:
                    max_args = int(constraint_lower.split(":", 1)[1])
                    if hasattr(context, "message") and hasattr(
                        context.message, "arguments"
                    ):
                        args = context.message.arguments or {}
                        if len(args) > max_args:
                            raise PolicyViolationError(
                                _deny_result(
                                    f"Constraint violation: max_args={max_args}, "
                                    f"got {len(args)} arguments"
                                )
                            )
                except (ValueError, IndexError):
                    logger.warning("Invalid max_args constraint: %s", constraint)
                continue

            if constraint_lower.startswith("require_metadata:"):
                required_key = constraint.split(":", 1)[1].strip()
                if hasattr(context, "message") and hasattr(
                    context.message, "arguments"
                ):
                    args = context.message.arguments or {}
                    if required_key not in args:
                        raise PolicyViolationError(
                            _deny_result(
                                f"Constraint violation: required metadata key "
                                f"'{required_key}' not present"
                            )
                        )
                continue

            if constraint_lower == "log_access":
                logger.info("Constrained access logged: %s", resource_id)
                continue

            # Unknown constraint — log but don't block
            logger.debug(
                "Unknown constraint '%s' for %s — ignored",
                constraint,
                resource_id,
            )


def _deny_result(reason: str) -> PolicyResult:
    """Create a DENY PolicyResult for error paths."""

    return PolicyResult(
        decision=PolicyDecision.DENY,
        reason=reason,
        policy_id="policy-enforcement-middleware",
    )


# Tags that opt a tool in to ``read_only`` policy constraints. Tools
# tagged with any of these are considered side-effect-free and may be
# invoked from sessions that policy has marked read-only.
_READ_ONLY_TAGS: frozenset[str] = frozenset({"read_only", "readonly", "safe"})


def _tool_is_readonly(tool_tags: frozenset[str]) -> bool:
    """Return True if any of the tool's tags declares it side-effect-free."""
    if not tool_tags:
        return False
    lowered = {t.lower() for t in tool_tags}
    return bool(lowered & _READ_ONLY_TAGS)


# Convention tag prefixes that map onto PolicyEvaluationContext
# capability fields. Tool authors and curators signal the capability
# surface of a tool via tags so the Policy Kernel can key its Rego /
# Cedar rules off a stable, serializable attribute instead of the
# caller having to thread fields down through every middleware.
_TAG_PREFIX_RESOURCE_TYPE = "resource:"
_TAG_PREFIX_ENVIRONMENT = "env:"
_TAG_PREFIX_RISK = "risk:"
_TAG_PREFIX_PRINCIPAL_TYPE = "principal:"
_TAG_PREFIX_ACTION = "action:"


def _capability_overrides(tags: frozenset[str], metadata: dict) -> dict[str, object]:
    """Translate capability-signaling tags/metadata into context kwargs.

    Three conventions, evaluated in priority order:

    1. Explicit ``capability`` dict on request metadata (from a
       curator-injected middleware) wins — it's the richest signal.
    2. ``resource:<type>`` / ``env:<env>`` / ``risk:<lvl>`` /
       ``principal:<type>`` tag prefixes next.
    3. Otherwise the PolicyEvaluationContext dataclass defaults apply.

    The approval fields are only ever set through metadata; tags are
    not trusted to claim approval.
    """
    overrides: dict[str, object] = {}

    # Path 2: tag prefixes.
    for tag in tags:
        lowered = tag.lower()
        if lowered.startswith(_TAG_PREFIX_RESOURCE_TYPE):
            overrides["resource_type"] = lowered[len(_TAG_PREFIX_RESOURCE_TYPE) :]
        elif lowered.startswith(_TAG_PREFIX_ENVIRONMENT):
            overrides["environment"] = lowered[len(_TAG_PREFIX_ENVIRONMENT) :]
        elif lowered.startswith(_TAG_PREFIX_RISK):
            overrides["risk"] = lowered[len(_TAG_PREFIX_RISK) :]
        elif lowered.startswith(_TAG_PREFIX_PRINCIPAL_TYPE):
            overrides["principal_type"] = lowered[len(_TAG_PREFIX_PRINCIPAL_TYPE) :]
        elif lowered.startswith(_TAG_PREFIX_ACTION):
            overrides["action"] = lowered[len(_TAG_PREFIX_ACTION) :]

    # Path 1: explicit metadata wins (overrides tags).
    cap_md = metadata.get("capability") if isinstance(metadata, dict) else None
    if isinstance(cap_md, dict):
        for field_name in (
            "action",
            "principal_type",
            "resource_type",
            "environment",
            "risk",
        ):
            if field_name in cap_md and isinstance(cap_md[field_name], str):
                overrides[field_name] = cap_md[field_name]
        if cap_md.get("approval_granted"):
            overrides["approval_granted"] = True
            ticket = cap_md.get("approval_ticket")
            if isinstance(ticket, str) and ticket:
                overrides["approval_ticket"] = ticket

    return overrides

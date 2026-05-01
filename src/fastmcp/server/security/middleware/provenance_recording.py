"""Provenance recording middleware for SecureMCP.

Automatically records all MCP operations in the provenance ledger.
Sits in the middleware chain to capture both inputs and outputs
(including errors) for complete audit trails.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import mcp.types as mt

from fastmcp.prompts.prompt import Prompt, PromptResult
from fastmcp.resources.resource import Resource, ResourceResult
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.middleware.middleware import (
    CallNext,
    Middleware,
    MiddlewareContext,
)
from fastmcp.server.security.provenance.ledger import ProvenanceLedger
from fastmcp.server.security.provenance.records import ProvenanceAction
from fastmcp.tools.tool import Tool, ToolResult

logger = logging.getLogger(__name__)


def _estimate_call_tokens(
    arguments: dict | None,
    result: ToolResult | None,
) -> tuple[int, int]:
    """Estimate input/output tokens for a tool call (chars/4 heuristic)."""
    import json as _json

    input_chars = len(_json.dumps(arguments or {}, separators=(",", ":"), default=str))

    output_chars = 0
    if result is not None:
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                output_chars += len(str(text))
        if result.structured_content:
            output_chars += len(
                _json.dumps(
                    result.structured_content, separators=(",", ":"), default=str
                )
            )

    return (max(1, input_chars // 4), max(1, output_chars // 4) if output_chars else 0)


class ProvenanceRecordingMiddleware(Middleware):
    """Middleware that records all MCP operations in the provenance ledger.

    Records both the request and response for each operation. On error,
    records the failure. This middleware should sit early in the chain
    (after auth/policy but before core handlers) to capture the full
    picture.

    Args:
        ledger: The ProvenanceLedger to record into.
        bypass_stdio: If True (default), skip recording for STDIO transport.
        record_list_operations: If True, record list operations too.
            Default is False (only record execution operations).
    """

    def __init__(
        self,
        ledger: ProvenanceLedger,
        *,
        bypass_stdio: bool = True,
        record_list_operations: bool = False,
    ) -> None:
        self.ledger = ledger
        self.bypass_stdio = bypass_stdio
        self.record_list_operations = record_list_operations

    def _should_bypass(self) -> bool:
        """Check if recording should be skipped for current transport."""
        if not self.bypass_stdio:
            return False
        from fastmcp.server.context import _current_transport

        return _current_transport.get() == "stdio"

    def _get_actor_id(self, context: MiddlewareContext) -> str:
        """Extract actor ID from middleware context."""
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
        if token is not None:
            return token.token[:8] + "..."
        return "anonymous"

    # ── Tool operations ──────────────────────────────────────────────

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Record tool call and its result."""
        if self._should_bypass():
            return await call_next(context)

        tool_name = context.message.name
        actor_id = self._get_actor_id(context)
        arguments = context.message.arguments or {}
        input_data = {
            "tool": tool_name,
            "arguments": arguments,
        }

        try:
            result = await call_next(context)

            input_tokens, output_tokens = _estimate_call_tokens(arguments, result)
            self.ledger.record(
                action=ProvenanceAction.TOOL_CALLED,
                actor_id=actor_id,
                resource_id=tool_name,
                input_data=input_data,
                output_data={"status": "success"},
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

            return result

        except Exception as exc:
            input_tokens, _ = _estimate_call_tokens(arguments, None)
            self.ledger.record(
                action=ProvenanceAction.ERROR,
                actor_id=actor_id,
                resource_id=tool_name,
                input_data=input_data,
                metadata={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "input_tokens": input_tokens,
                },
            )
            raise

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        """Optionally record tool listing."""
        tools = await call_next(context)

        if not self._should_bypass() and self.record_list_operations:
            self.ledger.record(
                action=ProvenanceAction.TOOL_CALLED,
                actor_id=self._get_actor_id(context),
                resource_id="__list_tools__",
                metadata={"tool_count": len(tools)},
            )

        return tools

    # ── Resource operations ──────────────────────────────────────────

    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, ResourceResult],
    ) -> ResourceResult:
        """Record resource read."""
        if self._should_bypass():
            return await call_next(context)

        uri = str(context.message.uri)
        actor_id = self._get_actor_id(context)

        try:
            result = await call_next(context)

            self.ledger.record(
                action=ProvenanceAction.RESOURCE_READ,
                actor_id=actor_id,
                resource_id=uri,
                input_data={"uri": uri},
                output_data={"status": "success"},
            )

            return result

        except Exception as exc:
            self.ledger.record(
                action=ProvenanceAction.ERROR,
                actor_id=actor_id,
                resource_id=uri,
                input_data={"uri": uri},
                metadata={"error": str(exc), "error_type": type(exc).__name__},
            )
            raise

    async def on_list_resources(
        self,
        context: MiddlewareContext[mt.ListResourcesRequest],
        call_next: CallNext[mt.ListResourcesRequest, Sequence[Resource]],
    ) -> Sequence[Resource]:
        """Optionally record resource listing."""
        resources = await call_next(context)

        if not self._should_bypass() and self.record_list_operations:
            self.ledger.record(
                action=ProvenanceAction.RESOURCE_LISTED,
                actor_id=self._get_actor_id(context),
                resource_id="__list_resources__",
                metadata={"resource_count": len(resources)},
            )

        return resources

    async def on_list_resource_templates(
        self,
        context: MiddlewareContext[mt.ListResourceTemplatesRequest],
        call_next: CallNext[
            mt.ListResourceTemplatesRequest, Sequence[ResourceTemplate]
        ],
    ) -> Sequence[ResourceTemplate]:
        """Pass through resource template listing."""
        return await call_next(context)

    # ── Prompt operations ────────────────────────────────────────────

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, PromptResult],
    ) -> PromptResult:
        """Record prompt render."""
        if self._should_bypass():
            return await call_next(context)

        prompt_name = context.message.name
        actor_id = self._get_actor_id(context)

        try:
            result = await call_next(context)

            self.ledger.record(
                action=ProvenanceAction.PROMPT_RENDERED,
                actor_id=actor_id,
                resource_id=prompt_name,
                input_data={
                    "prompt": prompt_name,
                    "arguments": context.message.arguments or {},
                },
                output_data={"status": "success"},
            )

            return result

        except Exception as exc:
            self.ledger.record(
                action=ProvenanceAction.ERROR,
                actor_id=actor_id,
                resource_id=prompt_name,
                metadata={"error": str(exc), "error_type": type(exc).__name__},
            )
            raise

    async def on_list_prompts(
        self,
        context: MiddlewareContext[mt.ListPromptsRequest],
        call_next: CallNext[mt.ListPromptsRequest, Sequence[Prompt]],
    ) -> Sequence[Prompt]:
        """Optionally record prompt listing."""
        prompts = await call_next(context)

        if not self._should_bypass() and self.record_list_operations:
            self.ledger.record(
                action=ProvenanceAction.PROMPT_LISTED,
                actor_id=self._get_actor_id(context),
                resource_id="__list_prompts__",
                metadata={"prompt_count": len(prompts)},
            )

        return prompts

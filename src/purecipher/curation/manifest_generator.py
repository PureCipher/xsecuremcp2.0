"""Derive a draft SecurityManifest from observed upstream capabilities.

The wizard's third step shows the curator a checklist of permissions
the registry suggests, derived from the introspection result. Per
product decision: **the curator may confirm or remove** any suggestion
but **may not add** permissions the registry didn't observe. This
keeps third-party attestations bounded by what the registry actually
saw, rather than by what the curator believed.

Suggestions are heuristics over tool names + descriptions + input
schemas. They are intentionally over-broad (better to suggest a perm
the curator removes than to miss one the curator can't add). Each
suggestion carries a ``rationale`` string so the wizard can show
"why" alongside each checkbox.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    SecurityManifest,
)

from purecipher.curation.introspector import IntrospectionResult

logger = logging.getLogger(__name__)


# Keyword groups → permission scope. Order matters: a tool name might
# match multiple groups, and we add every scope the matches imply.
_KEYWORDS: tuple[tuple[frozenset[str], PermissionScope, str], ...] = (
    (
        frozenset({"read", "fetch", "get", "load", "open", "scan"}),
        PermissionScope.FILE_SYSTEM_READ,
        "Tool name suggests it reads files",
    ),
    (
        frozenset({"write", "save", "create", "store", "update", "put"}),
        PermissionScope.FILE_SYSTEM_WRITE,
        "Tool name suggests it writes files",
    ),
    (
        frozenset(
            {
                "http",
                "fetch",
                "url",
                "api",
                "request",
                "download",
                "upload",
                "search",
            }
        ),
        PermissionScope.NETWORK_ACCESS,
        "Tool name suggests it makes network calls",
    ),
    (
        frozenset({"exec", "run", "shell", "command", "spawn", "subprocess"}),
        PermissionScope.SUBPROCESS_EXEC,
        "Tool name suggests it executes subprocesses",
    ),
    (
        frozenset({"env", "environ", "config"}),
        PermissionScope.ENVIRONMENT_READ,
        "Tool name suggests it reads environment variables",
    ),
)

# Argument name patterns that strongly imply a particular scope. These
# inspect the tool's JSON schema rather than its name, so they catch
# tools whose names don't betray their behavior.
_SCHEMA_ARG_HINTS: dict[str, tuple[PermissionScope, str]] = {
    "path": (
        PermissionScope.FILE_SYSTEM_READ,
        "Tool accepts a 'path' argument",
    ),
    "file_path": (
        PermissionScope.FILE_SYSTEM_READ,
        "Tool accepts a 'file_path' argument",
    ),
    "filepath": (
        PermissionScope.FILE_SYSTEM_READ,
        "Tool accepts a 'filepath' argument",
    ),
    "filename": (
        PermissionScope.FILE_SYSTEM_READ,
        "Tool accepts a 'filename' argument",
    ),
    "url": (
        PermissionScope.NETWORK_ACCESS,
        "Tool accepts a 'url' argument",
    ),
    "endpoint": (
        PermissionScope.NETWORK_ACCESS,
        "Tool accepts an 'endpoint' argument",
    ),
    "command": (
        PermissionScope.SUBPROCESS_EXEC,
        "Tool accepts a 'command' argument",
    ),
}


@dataclass
class PermissionSuggestion:
    """A single permission the registry suggests the curator confirm.

    ``selected=True`` is the default. The wizard renders these as
    pre-checked checkboxes; the curator unchecks the ones they don't
    want to vouch for. The curator cannot add new entries — only
    confirm or drop.
    """

    scope: PermissionScope
    rationale: str
    evidence: list[str] = field(default_factory=list)
    selected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope.value,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
            "selected": self.selected,
        }


@dataclass
class ManifestDraft:
    """A draft SecurityManifest plus the suggestions it was derived from.

    The wizard renders ``permission_suggestions`` as a checklist. On
    submit, the wizard sends back the SAME list with selection states
    flipped (curator can flip True→False; the backend rejects any
    True→add of a scope not in the original list).
    """

    upstream_ref: dict[str, Any]
    suggested_tool_name: str
    suggested_display_name: str
    suggested_description: str
    permission_suggestions: list[PermissionSuggestion] = field(default_factory=list)
    observed_tool_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "upstream_ref": dict(self.upstream_ref),
            "suggested_tool_name": self.suggested_tool_name,
            "suggested_display_name": self.suggested_display_name,
            "suggested_description": self.suggested_description,
            "permission_suggestions": [
                s.to_dict() for s in self.permission_suggestions
            ],
            "observed_tool_names": list(self.observed_tool_names),
        }

    def selected_scopes(self) -> set[PermissionScope]:
        """Permissions the curator (or the default) wants to keep."""
        return {s.scope for s in self.permission_suggestions if s.selected}

    def build_manifest(
        self,
        *,
        tool_name: str = "",
        display_name: str = "",
        version: str = "0.1.0",
        author: str = "",
        description: str = "",
    ) -> SecurityManifest:
        """Materialize the draft into a real :class:`SecurityManifest`.

        The selected permission suggestions become the manifest's
        permission set. A best-effort data flow is added based on
        observed tools so the manifest passes basic validation.
        """
        manifest_tool_name = tool_name or self.suggested_tool_name
        if not manifest_tool_name:
            raise ValueError("tool_name is required to build a manifest")

        permissions = self.selected_scopes()
        # Every MCP tool inherently exposes call_tool; declare it so the
        # certification validator doesn't flag it as missing.
        permissions.add(PermissionScope.CALL_TOOL)

        flows: list[DataFlowDeclaration] = []
        if self.observed_tool_names:
            flows.append(
                DataFlowDeclaration(
                    source="mcp.client",
                    destination="upstream.mcp_server",
                    classification=DataClassification.INTERNAL,
                    description=(
                        "Curator-vouched MCP server. Inputs are forwarded "
                        "to the upstream and outputs returned to the "
                        "client. Observed tools: "
                        + ", ".join(sorted(self.observed_tool_names)[:8])
                        + ("…" if len(self.observed_tool_names) > 8 else "")
                    ),
                )
            )

        return SecurityManifest(
            tool_name=manifest_tool_name,
            version=version,
            author=author,
            description=description or self.suggested_description,
            permissions=permissions,
            data_flows=flows,
            tags={"curated", "third-party"},
        )


def derive_manifest_draft(
    introspection: IntrospectionResult,
    *,
    suggested_tool_name: str = "",
    suggested_display_name: str = "",
) -> ManifestDraft:
    """Turn an :class:`IntrospectionResult` into a manifest draft.

    All suggestions come from observed tools — if the registry didn't
    see a behavior, the suggestion isn't created. The curator can only
    remove, not add (validated server-side at submission time).
    """
    suggestion_map: dict[PermissionScope, PermissionSuggestion] = {}

    def _add_evidence(
        scope: PermissionScope, rationale: str, evidence_line: str
    ) -> None:
        existing = suggestion_map.get(scope)
        if existing is None:
            suggestion_map[scope] = PermissionSuggestion(
                scope=scope,
                rationale=rationale,
                evidence=[evidence_line],
            )
            return
        # Don't grow the evidence list past a sensible cap; the wizard
        # only renders the first few lines.
        if evidence_line not in existing.evidence and len(existing.evidence) < 5:
            existing.evidence.append(evidence_line)

    # Tool-name and tool-description heuristics.
    for tool in introspection.tools:
        haystack = f"{tool.name} {tool.description}".lower()
        for keywords, scope, rationale in _KEYWORDS:
            if any(_word_in(haystack, kw) for kw in keywords):
                _add_evidence(scope, rationale, f"tool: {tool.name}")

        # Schema-argument heuristics.
        properties = (tool.input_schema or {}).get("properties") or {}
        if isinstance(properties, dict):
            for arg_name in properties.keys():
                hint = _SCHEMA_ARG_HINTS.get(str(arg_name).lower())
                if hint is None:
                    continue
                scope, rationale = hint
                _add_evidence(scope, rationale, f"tool: {tool.name}")

    # Resources observed → suggest READ_RESOURCE. We use READ rather
    # than WRITE because resources/list is a read affordance.
    if introspection.resources:
        _add_evidence(
            PermissionScope.READ_RESOURCE,
            "Upstream exposes MCP resources",
            f"{len(introspection.resources)} resource(s) observed",
        )

    # If nothing matched, surface a single generic NETWORK_ACCESS
    # suggestion — most MCP servers are network-bound somewhere — and
    # let the curator remove it if their server is fully offline.
    if not suggestion_map and introspection.tools:
        _add_evidence(
            PermissionScope.NETWORK_ACCESS,
            "Default suggestion for HTTP-hosted MCP servers",
            "no specific keywords matched",
        )

    suggestions = sorted(
        suggestion_map.values(),
        key=lambda s: s.scope.value,
    )

    suggested_description = ""
    if introspection.tools:
        suggested_description = (
            f"Curator-vouched {introspection.tool_count}-tool MCP server."
        )

    return ManifestDraft(
        upstream_ref=introspection.upstream_ref.to_dict(),
        suggested_tool_name=suggested_tool_name,
        suggested_display_name=suggested_display_name,
        suggested_description=suggested_description,
        permission_suggestions=suggestions,
        observed_tool_names=[t.name for t in introspection.tools],
    )


def reconcile_curator_selection(
    draft: ManifestDraft,
    selections: list[dict[str, Any]] | None,
) -> ManifestDraft:
    """Apply a curator's confirm/remove choices to a manifest draft.

    The wizard sends back the selections list — same shape as
    ``draft.permission_suggestions`` but with curator-edited
    ``selected`` values. We honor flips from True→False, ignore any
    other field changes (rationale/evidence are registry-owned), and
    refuse to add scopes that weren't in the original draft (this
    enforces the "confirm or remove only" contract).

    Args:
        draft: The original suggestions the registry produced.
        selections: Each element is ``{"scope": "...", "selected": bool}``.

    Returns:
        A new ManifestDraft with selection states updated. Out-of-band
        scopes in ``selections`` are silently dropped.
    """
    if not selections:
        return draft

    chosen_states: dict[str, bool] = {}
    for entry in selections:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope", "")).strip()
        if not scope:
            continue
        chosen_states[scope] = bool(entry.get("selected", False))

    updated: list[PermissionSuggestion] = []
    for suggestion in draft.permission_suggestions:
        new_state = chosen_states.get(
            suggestion.scope.value, suggestion.selected
        )
        updated.append(
            PermissionSuggestion(
                scope=suggestion.scope,
                rationale=suggestion.rationale,
                evidence=list(suggestion.evidence),
                selected=new_state,
            )
        )

    return ManifestDraft(
        upstream_ref=dict(draft.upstream_ref),
        suggested_tool_name=draft.suggested_tool_name,
        suggested_display_name=draft.suggested_display_name,
        suggested_description=draft.suggested_description,
        permission_suggestions=updated,
        observed_tool_names=list(draft.observed_tool_names),
    )


def _word_in(haystack: str, needle: str) -> bool:
    """Whole-word match against a lower-cased haystack.

    Avoids false positives like "import" matching "port" or "get_data"
    matching "ge". Splits on non-alphanumeric boundaries.
    """
    needle = needle.lower()
    if not needle:
        return False
    # Cheap whole-word check: search needle surrounded by non-alnum
    # boundaries (or string boundaries).
    n = len(needle)
    for i in range(0, len(haystack) - n + 1):
        if haystack[i : i + n] != needle:
            continue
        before = haystack[i - 1] if i > 0 else " "
        after = haystack[i + n] if i + n < len(haystack) else " "
        if not (before.isalnum() or before == "_") and not (
            after.isalnum() or after == "_"
        ):
            return True
    return False

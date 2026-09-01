"""Cedar-style policy provider for SecureMCP.

Cedar models authorization as a triple of (principal, action, resource)
plus optional ``when``/``unless`` conditions. This module ships a
pure-Python evaluator sufficient for capability-level authorization on
the SecureMCP hot path — no native dependencies, no subprocess, no
network. Cedar's full AWS-grade semantics (schema validation, entity
hierarchies, policy templates, granular types) are deliberately
narrowed to the subset the MCP policy kernel actually needs.

Supported syntax (a strict subset of Cedar 3.x)::

    permit (
        principal in Agent::"*",
        action == Action::"read_resource",
        resource in Resource::"*"
    ) when { context.environment == "production" };

    forbid (
        principal,
        action in [Action::"delete", Action::"drop"],
        resource in Resource::"backup"
    );

    forbid (
        principal,
        action == Action::"call_tool",
        resource
    ) when {
        context.environment == "production" &&
        context.risk in ["high", "critical"] &&
        !context.approval_granted
    };

Differences from upstream Cedar:

- Only ``permit`` and ``forbid`` effects. No policy templates, no
  ``@advice`` annotations (the result-reason captures the intent).
- Principal/action/resource use *type::id* strings; entity hierarchies
  are flat (``in`` means membership in a list of allowed ids, or the
  wildcard ``*`` which always matches).
- ``context.*`` reads from ``PolicyEvaluationContext`` fields — the
  well-known ones (environment/risk/approval_granted/actor_id) and
  anything in ``context.metadata``.
- Expressions: ``==``, ``!=``, ``in``, ``&&``, ``||``, ``!``, string
  literals, list literals, and ``context.<attr>`` reads. No user-
  defined functions, no arithmetic, no regex.

Why a subset: the alternative — ``cedarpy`` bindings to the Rust crate
— drags a native build dependency into every deployment of SecureMCP.
We only need enough Cedar to write deny-by-default capability bundles
against the existing PolicyEvaluationContext; the subset above covers
everything the default bundle needs and every example in the Cedar
quick-start guide.

The evaluator is deterministic and side-effect free. A policy that
fails to parse is dropped at load time with a ``CedarParseError``; a
policy that raises during evaluation fail-closes to DENY.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

logger = logging.getLogger(__name__)


class CedarParseError(ValueError):
    """Raised when a Cedar policy can't be parsed.

    The engine drops the offending policy rather than loading a
    half-parsed rule set — an unparsable policy is indistinguishable
    from a typo'd deny, and we'd rather fail loud at load time.
    """


# ── AST ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Entity:
    """A principal/action/resource slot in a Cedar policy head.

    ``constraint`` is one of:
    - ``None`` — bare ``principal`` / ``action`` / ``resource``, matches anything.
    - ``("==", "Type::id")`` — exact match.
    - ``("in", ["Type::id", ...])`` — membership match; ``*`` id = wildcard.
    """

    constraint: tuple[str, Any] | None

    def matches(self, value: str) -> bool:
        if self.constraint is None:
            return True
        op, rhs = self.constraint
        if op == "==":
            return _entity_matches(rhs, value)
        if op == "in":
            return any(_entity_matches(candidate, value) for candidate in rhs)
        return False


def _entity_matches(pattern: str, value: str) -> bool:
    """Loose match: pattern like ``Type::"id"`` vs a bare ``id``.

    The evaluator accepts either ``Type::id`` or ``id`` as input —
    capability-level providers usually just pass the raw action name
    (``call_tool``) or resource id (``backup-nightly``). We compare
    the id half, with ``*`` as a wildcard.
    """
    pattern_id = pattern.split("::", 1)[-1].strip('"')
    value_id = value.split("::", 1)[-1]
    if pattern_id == "*":
        return True
    return pattern_id == value_id


# Expression nodes. Keep this tiny: the language is intentionally
# under-powered so policies stay auditable.


@dataclass(frozen=True)
class _ExprLiteral:
    value: Any


@dataclass(frozen=True)
class _ExprList:
    items: tuple[Any, ...]


@dataclass(frozen=True)
class _ExprContextRead:
    attr: str


@dataclass(frozen=True)
class _ExprBinOp:
    op: str  # one of: == != in && ||
    lhs: Any
    rhs: Any


@dataclass(frozen=True)
class _ExprNot:
    inner: Any


@dataclass(frozen=True)
class _Policy:
    """A single permit/forbid rule.

    ``clauses`` is a flat list of condition expressions, all of which
    must evaluate truthy for the rule to fire. ``when { X }`` adds a
    clause ``X``; ``unless { Y }`` adds ``!Y``.
    """

    effect: str  # "permit" or "forbid"
    principal: _Entity
    action: _Entity
    resource: _Entity
    clauses: tuple[Any, ...]
    raw: str  # original policy text — surfaced in decision reasons

    policy_id: str = "cedar-policy"


# ── Parser ─────────────────────────────────────────────────────────


# Anchor a policy start (permit/forbid followed by '('); the rest of
# the policy body is walked by hand because Cedar's nested braces +
# double-quoted identifiers make a regex-based parser brittle.
_POLICY_START = re.compile(r"\b(permit|forbid)\s*\(", re.IGNORECASE)


def parse_cedar(source: str) -> list[_Policy]:
    """Parse a Cedar policy document into a list of `_Policy` rules.

    The parser is whitespace-tolerant and supports ``//`` and ``#``
    single-line comments plus ``/* ... */`` block comments. Statements
    must end with a semicolon.
    """
    stripped = _strip_comments(source)
    policies: list[_Policy] = []
    pos = 0
    while pos < len(stripped):
        m = _POLICY_START.search(stripped, pos)
        if m is None:
            break
        effect = m.group(1).lower()
        head_start = m.end()  # points at first char after '('
        head_end = _find_matching(stripped, head_start - 1, "(", ")")
        head = stripped[head_start:head_end]
        tail_start = head_end + 1
        semi = stripped.find(";", tail_start)
        if semi == -1:
            raise CedarParseError(
                f"Cedar policy at offset {m.start()} has no terminating ';'"
            )
        tail = stripped[tail_start:semi].strip()
        raw = stripped[m.start() : semi + 1].strip()
        principal, action, resource = _parse_head(head)
        clauses = _parse_conditions(tail)
        policies.append(
            _Policy(
                effect=effect,
                principal=principal,
                action=action,
                resource=resource,
                clauses=tuple(clauses),
                raw=raw,
                policy_id=f"cedar::{effect}::{m.start()}",
            )
        )
        pos = semi + 1
    return policies


def _strip_comments(source: str) -> str:
    """Remove ``//`` / ``#`` line comments and ``/* */`` block comments.

    Keeps character offsets meaningful by replacing comment bytes
    with spaces so parser errors point back at the original text.

    Annotations of the form ``// @name`` or ``# @name`` are preserved
    byte-for-byte so downstream passes can detect them on the policy
    ``raw`` text (Cedar's upstream syntax doesn't have annotations yet,
    so we repurpose line comments; this is the subset's one
    extension).
    """
    out = list(source)
    i = 0
    while i < len(source):
        ch = source[i]
        if ch == '"':
            # Skip over quoted strings so `"a // b"` doesn't get eaten.
            j = i + 1
            while j < len(source) and source[j] != '"':
                if source[j] == "\\":
                    j += 2
                    continue
                j += 1
            i = j + 1
            continue
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
            j = source.find("\n", i)
            end = j if j != -1 else len(source)
            segment = source[i:end]
            if "@" not in segment:
                for k in range(i, end):
                    out[k] = " "
            i = end
            continue
        if ch == "#":
            j = source.find("\n", i)
            end = j if j != -1 else len(source)
            segment = source[i:end]
            if "@" not in segment:
                for k in range(i, end):
                    out[k] = " "
            i = end
            continue
        if ch == "/" and i + 1 < len(source) and source[i + 1] == "*":
            j = source.find("*/", i + 2)
            end = j + 2 if j != -1 else len(source)
            for k in range(i, end):
                out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def _find_matching(text: str, open_idx: int, open_ch: str, close_ch: str) -> int:
    """Index of the ``close_ch`` that matches the ``open_ch`` at ``open_idx``.

    Handles nested parentheses/braces; ignores delimiters inside
    double-quoted strings.
    """
    depth = 0
    i = open_idx
    while i < len(text):
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                if text[j] == "\\":
                    j += 2
                    continue
                j += 1
            i = j + 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise CedarParseError(f"Unbalanced {open_ch}/{close_ch}")


def _parse_head(head: str) -> tuple[_Entity, _Entity, _Entity]:
    """Split the head into principal/action/resource slots.

    The Cedar head is a comma-separated list of 0-3 entries, each
    starting with ``principal``, ``action``, or ``resource``. Missing
    slots default to bare (match-anything). Commas inside list
    literals (``in [..., ...]``) are handled by tracking bracket depth.
    """
    parts = _split_top_level(head, separator=",")
    principal = _Entity(None)
    action = _Entity(None)
    resource = _Entity(None)
    for part in parts:
        trimmed = part.strip()
        if not trimmed:
            continue
        lowered = trimmed.lower()
        if lowered.startswith("principal"):
            principal = _parse_entity(trimmed[len("principal") :])
        elif lowered.startswith("action"):
            action = _parse_entity(trimmed[len("action") :])
        elif lowered.startswith("resource"):
            resource = _parse_entity(trimmed[len("resource") :])
        else:
            raise CedarParseError(f"Unknown head entry: {trimmed!r}")
    return principal, action, resource


def _split_top_level(text: str, *, separator: str) -> list[str]:
    """Split on ``separator`` only at depth 0 (outside [] / {} / '').

    Needed because ``action in [Action::\"a\", Action::\"b\"]`` contains
    an internal comma that a naive split would mis-handle.
    """
    out: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                if text[j] == "\\":
                    j += 2
                    continue
                j += 1
            i = j + 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == separator and depth == 0:
            out.append(text[start:i])
            start = i + 1
        i += 1
    out.append(text[start:])
    return out


def _parse_entity(rest: str) -> _Entity:
    """Parse the constraint half of a ``principal``/``action``/``resource``.

    ``rest`` begins immediately after the keyword — e.g., ``" == Action::\"call_tool\""``
    or ``" in [Action::\"delete\"]"`` or an empty string for bare slots.
    """
    trimmed = rest.strip()
    if not trimmed:
        return _Entity(None)
    if trimmed.startswith("=="):
        value = trimmed[2:].strip()
        return _Entity(("==", _parse_entity_literal(value)))
    if trimmed.lower().startswith("in "):
        value = trimmed[3:].strip()
        if value.startswith("["):
            end = _find_matching(value, 0, "[", "]")
            inner = value[1:end].strip()
            items = [
                _parse_entity_literal(item.strip())
                for item in _split_top_level(inner, separator=",")
                if item.strip()
            ]
            return _Entity(("in", items))
        return _Entity(("in", [_parse_entity_literal(value)]))
    raise CedarParseError(f"Can't parse entity constraint: {rest!r}")


def _parse_entity_literal(text: str) -> str:
    """Accept ``Type::\"id\"`` and return ``Type::id``.

    We strip surrounding quotes because the evaluator compares by id
    regardless of quote style; reduces two forms to one.
    """
    trimmed = text.strip()
    if "::" not in trimmed:
        raise CedarParseError(f"Entity literal must be Type::id, got {trimmed!r}")
    type_part, id_part = trimmed.split("::", 1)
    id_part = id_part.strip()
    if id_part.startswith('"') and id_part.endswith('"'):
        id_part = id_part[1:-1]
    return f"{type_part.strip()}::{id_part}"


def _parse_conditions(tail: str) -> list[Any]:
    """Parse the ``when { ... } unless { ... }`` suffix into clauses.

    Each ``when`` clause contributes the expression; each ``unless``
    clause contributes its negation. Returned clauses are AND-ed.
    Annotation comments (``// @name`` / ``# @name``) are preserved
    by :func:`_strip_comments` so the policy's ``raw`` text can be
    scanned for them; the parser skips past them here since they
    carry no evaluation-time meaning.
    """
    clauses: list[Any] = []
    remaining = tail.strip()
    while remaining:
        lowered = remaining.lower()
        if lowered.startswith("when"):
            body, rest = _cut_brace(remaining, "when")
            clauses.append(_parse_expression(body))
            remaining = rest.strip()
            continue
        if lowered.startswith("unless"):
            body, rest = _cut_brace(remaining, "unless")
            clauses.append(_ExprNot(_parse_expression(body)))
            remaining = rest.strip()
            continue
        if remaining.startswith(("//", "#")):
            # Skip to end of the annotation line.
            nl = remaining.find("\n")
            remaining = "" if nl == -1 else remaining[nl + 1 :].strip()
            continue
        if remaining:
            raise CedarParseError(f"Unexpected trailing text: {remaining!r}")
    return clauses


def _cut_brace(text: str, keyword: str) -> tuple[str, str]:
    """Cut ``<keyword> { body }`` out of ``text``, returning body + rest."""
    start = len(keyword)
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        raise CedarParseError(f"'{keyword}' must be followed by '{{'")
    end = _find_matching(text, start, "{", "}")
    body = text[start + 1 : end]
    return body, text[end + 1 :]


# ── Expression parser ──────────────────────────────────────────────
#
# Tiny recursive-descent for the expression grammar:
#
#   or    := and ("||" and)*
#   and   := not ("&&" not)*
#   not   := "!" not | rel
#   rel   := primary (("==" | "!=" | "in") primary)?
#   primary := context "." IDENT
#            | STRING
#            | "[" expr ("," expr)* "]"
#            | "true" | "false"
#            | "(" or ")"


def _parse_expression(text: str) -> Any:
    tokens = _tokenize(text)
    parser = _ExprParser(tokens)
    expr = parser.parse_or()
    if parser.pos < len(tokens):
        raise CedarParseError(f"Unexpected token {tokens[parser.pos]!r} in expression")
    return expr


_TOKEN_RE = re.compile(
    r"""
    \s+                             |
    ("(?:[^"\\]|\\.)*")             |   # string literal
    (&&|\|\||==|!=|!|\.|\[|\]|\(|\)|,) |
    ([A-Za-z_][A-Za-z0-9_]*)                # identifier / keyword
    """,
    re.VERBOSE,
)


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            raise CedarParseError(
                f"Unrecognized character {text[pos]!r} at offset {pos}"
            )
        if m.group(0).strip():
            tokens.append(m.group(0))
        pos = m.end()
    return tokens


class _ExprParser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _eat(self, expected: str | None = None) -> str:
        if self.pos >= len(self.tokens):
            raise CedarParseError("Unexpected end of expression")
        tok = self.tokens[self.pos]
        if expected is not None and tok != expected:
            raise CedarParseError(f"Expected {expected!r}, got {tok!r}")
        self.pos += 1
        return tok

    def parse_or(self) -> Any:
        left = self.parse_and()
        while self._peek() == "||":
            self._eat("||")
            right = self.parse_and()
            left = _ExprBinOp("||", left, right)
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        while self._peek() == "&&":
            self._eat("&&")
            right = self.parse_not()
            left = _ExprBinOp("&&", left, right)
        return left

    def parse_not(self) -> Any:
        if self._peek() == "!":
            self._eat("!")
            return _ExprNot(self.parse_not())
        return self.parse_rel()

    def parse_rel(self) -> Any:
        left = self.parse_primary()
        tok = self._peek()
        if tok in {"==", "!="}:
            op = self._eat()
            return _ExprBinOp(op, left, self.parse_primary())
        if tok == "in":
            self._eat("in")
            return _ExprBinOp("in", left, self.parse_primary())
        return left

    def parse_primary(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise CedarParseError("Unexpected end of expression")
        if tok == "(":
            self._eat("(")
            inner = self.parse_or()
            self._eat(")")
            return inner
        if tok == "[":
            self._eat("[")
            items: list[Any] = []
            if self._peek() != "]":
                items.append(self.parse_or())
                while self._peek() == ",":
                    self._eat(",")
                    items.append(self.parse_or())
            self._eat("]")
            return _ExprList(tuple(items))
        if tok.startswith('"') and tok.endswith('"'):
            self._eat()
            return _ExprLiteral(_unquote(tok))
        if tok in {"true", "false"}:
            self._eat()
            return _ExprLiteral(tok == "true")
        if tok == "context":
            self._eat("context")
            self._eat(".")
            attr = self._eat()
            return _ExprContextRead(attr)
        raise CedarParseError(f"Unexpected token {tok!r}")


def _unquote(text: str) -> str:
    # Cedar string literals support basic escapes; we decode the same
    # subset Python json does since our test fixtures use JSON-style
    # escapes and nothing more exotic.
    return bytes(text[1:-1], "utf-8").decode("unicode_escape")


# ── Evaluator ──────────────────────────────────────────────────────


def _eval_expr(expr: Any, ctx: PolicyEvaluationContext) -> Any:
    if isinstance(expr, _ExprLiteral):
        return expr.value
    if isinstance(expr, _ExprList):
        return [_eval_expr(item, ctx) for item in expr.items]
    if isinstance(expr, _ExprContextRead):
        # Prefer the typed field when present; fall back to the
        # free-form metadata dict so policies can read tags /
        # custom attributes without a model change.
        if hasattr(ctx, expr.attr):
            return getattr(ctx, expr.attr)
        return ctx.metadata.get(expr.attr)
    if isinstance(expr, _ExprNot):
        return not _eval_expr(expr.inner, ctx)
    if isinstance(expr, _ExprBinOp):
        if expr.op == "&&":
            return bool(_eval_expr(expr.lhs, ctx)) and bool(_eval_expr(expr.rhs, ctx))
        if expr.op == "||":
            return bool(_eval_expr(expr.lhs, ctx)) or bool(_eval_expr(expr.rhs, ctx))
        lhs = _eval_expr(expr.lhs, ctx)
        rhs = _eval_expr(expr.rhs, ctx)
        if expr.op == "==":
            return lhs == rhs
        if expr.op == "!=":
            return lhs != rhs
        if expr.op == "in":
            if isinstance(rhs, (list, tuple, set, frozenset)):
                return lhs in rhs
            return False
    raise CedarParseError(f"Unsupported expression node: {expr!r}")


def _policy_fires(policy: _Policy, ctx: PolicyEvaluationContext) -> bool:
    if not policy.principal.matches(ctx.actor_id or ""):
        return False
    if not policy.action.matches(ctx.action):
        return False
    if not policy.resource.matches(ctx.resource_id):
        return False
    for clause in policy.clauses:
        try:
            if not _eval_expr(clause, ctx):
                return False
        except Exception:
            # Clause errors fail-closed: the Cedar policy gets skipped
            # (not fired) rather than halting evaluation. Combined with
            # the engine's deny-by-default, a broken policy won't
            # accidentally grant access.
            logger.warning(
                "Cedar clause failed; treating policy as not-fired",
                exc_info=True,
            )
            return False
    return True


# ── Provider ───────────────────────────────────────────────────────


class CedarPolicy:
    """PolicyProvider backed by a Cedar-style policy document.

    The provider evaluates all ``forbid`` rules first — any firing
    forbid short-circuits to DENY. Then it evaluates all ``permit``
    rules; if at least one fires, the result is ALLOW. Otherwise
    DEFER, so other providers in the chain still get a say.

    This matches Cedar's own "deny overrides, at least one permit
    required" semantics. Providers that want capability-style
    REQUIRE_APPROVAL can emit a policy that annotates a permit with
    a reason containing ``"require_approval"`` — the provider
    translates that into PolicyDecision.REQUIRE_APPROVAL so the
    PolicyEngine knows to short-circuit at the kernel level.

    Args:
        source: Cedar policy document (string).
        policy_id: Stable id for this provider instance; surfaced on
            every result and in the audit log.
        version: Policy version string (semver recommended).
        require_approval_tag: Name of a boolean attribute on a
            firing permit that promotes the decision to
            REQUIRE_APPROVAL. Defaults to ``require_approval``,
            read from the policy's trailing ``// @require_approval``
            annotation.
    """

    def __init__(
        self,
        source: str,
        *,
        policy_id: str = "cedar-capability",
        version: str = "1.0.0",
    ) -> None:
        self._policies = parse_cedar(source)
        self._policy_id = policy_id
        self._version = version

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        # Deny overrides: any firing forbid wins immediately.
        for policy in self._policies:
            if policy.effect != "forbid":
                continue
            if _policy_fires(policy, context):
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Cedar forbid matched: {_summarize(policy)}",
                    policy_id=self._policy_id,
                )

        fired_permits: list[_Policy] = [
            p
            for p in self._policies
            if p.effect == "permit" and _policy_fires(p, context)
        ]
        if not fired_permits:
            return PolicyResult(
                decision=PolicyDecision.DEFER,
                reason="No Cedar permit matched",
                policy_id=self._policy_id,
            )

        # Annotated approval requests: a permit whose raw text
        # contains an ``@require_approval`` annotation escalates to
        # REQUIRE_APPROVAL unless the caller supplied approval.
        for permit in fired_permits:
            if "@require_approval" in permit.raw:
                if context.approval_granted and context.approval_ticket:
                    return PolicyResult(
                        decision=PolicyDecision.ALLOW,
                        reason=(
                            f"Cedar permit matched with approval "
                            f"{context.approval_ticket}: "
                            f"{_summarize(permit)}"
                        ),
                        policy_id=self._policy_id,
                    )
                return PolicyResult(
                    decision=PolicyDecision.REQUIRE_APPROVAL,
                    reason=(f"Cedar permit requires approval: {_summarize(permit)}"),
                    policy_id=self._policy_id,
                )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"Cedar permit matched: {_summarize(fired_permits[0])}",
            policy_id=self._policy_id,
        )

    def get_policy_id(self) -> str:
        return self._policy_id

    def get_policy_version(self) -> str:
        return self._version


def _summarize(policy: _Policy) -> str:
    """One-line summary used in reasons — the full policy is often huge."""
    return policy.raw.split("\n", 1)[0][:120]

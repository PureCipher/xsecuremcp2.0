"""Rego-style policy provider for SecureMCP.

Two flavors ship in this module:

- :class:`RegoPolicy` — a pure-Python evaluator for a minimal Rego
  subset. Enough to express deny-by-default capability rules against
  the standard ``input`` shape emitted by the MCP policy kernel. Zero
  external deps. Meant to be the default on every deployment.
- :class:`OPAHttpRegoPolicy` — a thin adapter that forwards
  evaluation to an external OPA daemon via its Data REST API. Pick
  this when you already run OPA alongside your services and want full
  Rego compatibility.

The two providers expose the same :class:`PolicyProvider` interface
and can be composed interchangeably. The capability bundle loader
selects between them based on how it was constructed.

What the built-in subset does NOT cover:

- Virtual documents / imports / user-defined functions.
- ``with`` modifiers, partial evaluation, future.keywords.
- Numeric operators beyond equality and membership.
- Regex (intentional — keeps policies auditable).

If your policy needs any of the above, either stick with Cedar for
that rule set or point the loader at a real OPA daemon.

Input contract
==============

The built-in evaluator calls policies with an ``input`` document
shaped like::

    input = {
        "actor_id": "agent-foo",
        "action": "call_tool",
        "resource_id": "prod-db-prune",
        "principal_type": "agent",
        "resource_type": "database",
        "environment": "production",
        "risk": "high",
        "approval_granted": False,
        "approval_ticket": None,
        "tags": ["write", "irreversible"],
        "metadata": {...},
    }

Policies return a rule named ``allow``, ``deny``, or
``require_approval`` — only one may fire per evaluation. Multiple
matching deny rules collapse to a single DENY with reasons joined.

Example policy::

    package securemcp.capability

    default allow = false

    allow {
        input.environment == "staging"
    }

    deny[msg] {
        input.action == "delete_backup"
        msg := "backup deletion is never allowed"
    }

    require_approval[msg] {
        input.environment == "production"
        input.resource_type in {"database", "cluster", "secret"}
        not input.approval_granted
        msg := sprintf("prod write to %s requires approval", [input.resource_id])
    }
"""

from __future__ import annotations

import json
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


class RegoParseError(ValueError):
    """Raised when a Rego policy can't be parsed by the built-in subset."""


# ── AST ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _InputRef:
    """Represents ``input.<path>.<path>...`` in a Rego expression.

    Path segments are evaluated against the input document at
    decision time; a missing segment resolves to ``None`` (falsy in
    Rego too).
    """

    path: tuple[str, ...]


@dataclass(frozen=True)
class _Literal:
    value: Any


@dataclass(frozen=True)
class _Set:
    items: tuple[Any, ...]


@dataclass(frozen=True)
class _RegoArgList:
    """Ordered argument list used by ``sprintf(..., [a, b])``.

    Distinct from :class:`_Set` because Rego lists preserve order and
    commonly contain :class:`_InputRef` elements that need late
    resolution at evaluation time.
    """

    items: tuple[Any, ...]


@dataclass(frozen=True)
class _Call:
    """A built-in function call. Only ``sprintf`` and ``startswith``
    are supported; a third-party rule using anything else fails parse.
    """

    name: str
    args: tuple[Any, ...]


@dataclass(frozen=True)
class _BinOp:
    op: str  # ==, !=, in, ":="
    lhs: Any
    rhs: Any


@dataclass(frozen=True)
class _NotExpr:
    inner: Any


@dataclass(frozen=True)
class _Rule:
    """A single rule body.

    ``head`` is one of:
    - ``("default_allow", <default_value>)`` — a ``default allow = x`` line.
    - ``("allow",)`` / ``("deny", msg_var)`` / ``("require_approval", msg_var)``.

    ``body`` is a list of expressions, all of which must be truthy
    for the rule to fire.
    """

    head: tuple[Any, ...]
    body: tuple[Any, ...]
    raw: str


@dataclass(frozen=True)
class _Module:
    package: str
    rules: tuple[_Rule, ...]


# ── Parser ─────────────────────────────────────────────────────────
#
# Rego is whitespace-significant at the statement level (each line of
# a rule body is an independent expression). We strip comments, then
# walk rules by matching the head regex and harvesting the braced
# body that follows.


_RULE_HEAD = re.compile(
    r"""^(?P<default>default\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)
        (?:\s*\[(?P<key>[A-Za-z_][A-Za-z0-9_]*)\])?
        (?:\s*(?P<eq>=|:=)\s*(?P<value>[^{]+?))?
        \s*(?P<body>\{)?\s*$""",
    re.VERBOSE,
)


def parse_rego(source: str) -> _Module:
    cleaned = _strip_line_comments(source)
    lines = cleaned.splitlines()

    package = "default"
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("package "):
            package = stripped[len("package ") :].strip()
            i += 1
            break
        # Tolerate ``import`` statements by skipping them — we don't
        # support imports, but refusing to parse would mean rejecting
        # most real-world Rego modules copied in from snippets.
        if stripped.startswith("import "):
            i += 1
            continue
        break

    rules: list[_Rule] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        match = _RULE_HEAD.match(stripped)
        if not match:
            raise RegoParseError(
                f"Unrecognized Rego statement at line {i + 1}: {stripped!r}"
            )

        default = bool(match.group("default"))
        name = match.group("name")
        key = match.group("key")
        eq_value = match.group("value")
        has_body = bool(match.group("body"))

        if default:
            # ``default allow = false`` — no body.
            raw_value = (eq_value or "false").strip()
            rules.append(
                _Rule(
                    head=("default", name, _parse_atom(raw_value)),
                    body=(),
                    raw=stripped,
                )
            )
            i += 1
            continue

        if not has_body:
            # Shorthand rule ``allow = true`` with no body is a
            # default-true allow. We don't support other headless
            # rules (they rarely appear in capability policies).
            if eq_value is not None:
                rules.append(
                    _Rule(
                        head=(name, key, _parse_atom(eq_value.strip())),
                        body=(),
                        raw=stripped,
                    )
                )
                i += 1
                continue
            raise RegoParseError(
                f"Rego rule {name!r} at line {i + 1} has neither body nor value"
            )

        body_lines, j = _collect_body(lines, i)
        body_exprs = tuple(
            _parse_expression(ln) for ln in body_lines if ln.strip()
        )
        rules.append(
            _Rule(
                head=(name, key) if key else (name,),
                body=body_exprs,
                raw="\n".join([lines[i], *body_lines, lines[j]]),
            )
        )
        i = j + 1

    return _Module(package=package, rules=tuple(rules))


def _strip_line_comments(source: str) -> str:
    out_lines: list[str] = []
    for line in source.splitlines():
        idx = -1
        in_string = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"':
                in_string = not in_string
            elif ch == "#" and not in_string:
                idx = i
                break
            i += 1
        out_lines.append(line[:idx] if idx >= 0 else line)
    return "\n".join(out_lines)


def _collect_body(lines: list[str], start: int) -> tuple[list[str], int]:
    """Return body lines and the index of the closing ``}`` line."""
    body: list[str] = []
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if line.strip() == "}":
            return body, j
        body.append(line)
        j += 1
    raise RegoParseError(
        f"Rego rule starting at line {start + 1} has no closing '}}'"
    )


def _parse_expression(raw: str) -> Any:
    """Parse a single rule-body line into an AST node.

    The Rego subset treats each body line as an independent expression.
    Supported shapes, one per line (see module docstring for full
    semantics): an equality or inequality between an input reference
    and a literal, an ``in`` membership test against a set, a
    ``not`` prefix, an assignment with ``:=``, or a ``sprintf`` /
    ``startswith`` call. Anything else raises :class:`RegoParseError`.
    """
    text = raw.strip()
    if not text:
        return _Literal(True)

    if text.startswith("not "):
        return _NotExpr(_parse_expression(text[4:].strip()))

    # assignment (``msg := ...``) — used by deny[msg]/require_approval[msg].
    assign = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*(.+)$", text)
    if assign:
        return _BinOp(":=", assign.group(1), _parse_atom(assign.group(2)))

    # Function-call-only line (no surrounding operator).
    if text.startswith("startswith("):
        return _parse_call(text)

    # Binary: splits on the first top-level ==, !=, or ``in``.
    for op in ("==", "!=", " in "):
        idx = _find_top_level(text, op)
        if idx is not None:
            lhs = text[:idx].strip()
            rhs = text[idx + len(op) :].strip()
            return _BinOp(op.strip(), _parse_atom(lhs), _parse_atom(rhs))

    return _parse_atom(text)


def _find_top_level(text: str, needle: str) -> int | None:
    depth = 0
    i = 0
    while i < len(text) - len(needle) + 1:
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
        elif depth == 0 and text[i : i + len(needle)] == needle:
            return i
        i += 1
    return None


def _parse_atom(text: str) -> Any:
    text = text.strip()
    if text.startswith("input"):
        parts = text.split(".")
        return _InputRef(tuple(parts[1:]))
    if text.startswith(("sprintf(", "startswith(")):
        return _parse_call(text)
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1]
        items: list[Any] = []
        if inner.strip():
            items.extend(
                _parse_atom(piece) for piece in _split_top_level(inner, ",")
            )
        return _Set(tuple(items))
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        items: list[Any] = []
        if inner.strip():
            items.extend(
                _parse_atom(piece) for piece in _split_top_level(inner, ",")
            )
        # Use a dedicated list node so the evaluator knows to recurse
        # into each element — sprintf arg lists contain _InputRef
        # nodes that must resolve against the input document at
        # evaluation time, not parse time.
        return _RegoArgList(tuple(items))
    if text.startswith('"') and text.endswith('"'):
        return _Literal(
            bytes(text[1:-1], "utf-8").decode("unicode_escape")
        )
    if text in {"true", "false"}:
        return _Literal(text == "true")
    if text == "null":
        return _Literal(None)
    # Try numeric literal.
    try:
        if "." in text:
            return _Literal(float(text))
        return _Literal(int(text))
    except ValueError:
        pass
    raise RegoParseError(f"Unrecognized atom: {text!r}")


def _parse_call(text: str) -> _Call:
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$", text, re.DOTALL)
    if not m:
        raise RegoParseError(f"Malformed call: {text!r}")
    name = m.group(1)
    raw_args = m.group(2)
    args: list[Any] = []
    if raw_args.strip():
        args.extend(
            _parse_atom(piece) for piece in _split_top_level(raw_args, ",")
        )
    return _Call(name=name, args=tuple(args))


def _split_top_level(text: str, separator: str) -> list[str]:
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
    return [p.strip() for p in out]


# ── Evaluator ──────────────────────────────────────────────────────


def _context_to_input(ctx: PolicyEvaluationContext) -> dict[str, Any]:
    """Project the evaluation context into the Rego input document.

    Mirrors the shape documented at the module header so policy
    authors can rely on a stable schema.
    """
    return {
        "actor_id": ctx.actor_id or "",
        "action": ctx.action,
        "resource_id": ctx.resource_id,
        "principal_type": getattr(ctx, "principal_type", "agent"),
        "resource_type": getattr(ctx, "resource_type", "tool"),
        "environment": getattr(ctx, "environment", "production"),
        "risk": getattr(ctx, "risk", "low"),
        "approval_granted": bool(getattr(ctx, "approval_granted", False)),
        "approval_ticket": getattr(ctx, "approval_ticket", None),
        "tags": sorted(ctx.tags),
        "metadata": dict(ctx.metadata),
    }


def _eval_atom(node: Any, bindings: dict[str, Any], input_doc: dict[str, Any]) -> Any:
    if isinstance(node, _Literal):
        return node.value
    if isinstance(node, _Set):
        return {_eval_atom(i, bindings, input_doc) for i in node.items}
    if isinstance(node, _RegoArgList):
        return [_eval_atom(i, bindings, input_doc) for i in node.items]
    if isinstance(node, _InputRef):
        cursor: Any = input_doc
        for seg in node.path:
            if isinstance(cursor, dict):
                cursor = cursor.get(seg)
            else:
                return None
        return cursor
    if isinstance(node, _Call):
        if node.name == "sprintf":
            fmt = _eval_atom(node.args[0], bindings, input_doc)
            values = _eval_atom(node.args[1], bindings, input_doc)
            if not isinstance(fmt, str):
                return ""
            args = list(values) if isinstance(values, list) else [values]
            return _rego_sprintf(fmt, args)
        if node.name == "startswith":
            s = _eval_atom(node.args[0], bindings, input_doc) or ""
            prefix = _eval_atom(node.args[1], bindings, input_doc) or ""
            return isinstance(s, str) and s.startswith(str(prefix))
        raise RegoParseError(f"Unsupported builtin: {node.name}")
    if isinstance(node, str):
        # Bare identifier (variable binding) — resolved from the local
        # bindings dict; unknown names are treated as None (Rego's
        # undefined).
        return bindings.get(node)
    return node


def _rego_sprintf(fmt: str, args: list[Any]) -> str:
    # Minimal OPA sprintf: %s and %d, in argument order.
    out: list[str] = []
    i = 0
    arg_idx = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "%" and i + 1 < len(fmt):
            code = fmt[i + 1]
            if code in {"s", "d", "v"} and arg_idx < len(args):
                out.append(str(args[arg_idx]))
                arg_idx += 1
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _eval_expression(
    node: Any,
    bindings: dict[str, Any],
    input_doc: dict[str, Any],
) -> bool:
    if isinstance(node, _BinOp):
        if node.op == ":=":
            bindings[node.lhs] = _eval_atom(node.rhs, bindings, input_doc)
            return True
        lhs = _eval_atom(node.lhs, bindings, input_doc)
        rhs = _eval_atom(node.rhs, bindings, input_doc)
        if node.op == "==":
            return lhs == rhs
        if node.op == "!=":
            return lhs != rhs
        if node.op == "in":
            if isinstance(rhs, (set, frozenset, list, tuple)):
                return lhs in rhs
            return False
        return False
    if isinstance(node, _NotExpr):
        return not _eval_expression(node.inner, bindings, input_doc)
    if isinstance(node, _Call):
        return bool(_eval_atom(node, bindings, input_doc))
    if isinstance(node, _Literal):
        return bool(node.value)
    if isinstance(node, _InputRef):
        return bool(_eval_atom(node, bindings, input_doc))
    return False


# ── Provider ───────────────────────────────────────────────────────


class RegoPolicy:
    """PolicyProvider backed by a Rego module.

    Rules named ``deny`` produce PolicyDecision.DENY (one firing rule
    short-circuits); rules named ``require_approval`` produce
    PolicyDecision.REQUIRE_APPROVAL; rules named ``allow`` produce
    ALLOW. When no rule fires the provider returns DEFER so a
    subsequent provider in the chain can allow or deny.

    Args:
        source: The Rego module source text.
        policy_id: Stable id surfaced in results and audit.
        version: Version tag for the provider (semver recommended).
    """

    def __init__(
        self,
        source: str,
        *,
        policy_id: str = "rego-capability",
        version: str = "1.0.0",
    ) -> None:
        self._module = parse_rego(source)
        self._policy_id = policy_id
        self._version = version

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        input_doc = _context_to_input(context)

        # Pass 1: deny wins. Collect every firing deny so the reason
        # reflects the actual policy authors' intent (first match).
        for rule in self._module.rules:
            if rule.head[0] != "deny":
                continue
            bindings: dict[str, Any] = {}
            if _all_body_exprs_true(rule, bindings, input_doc):
                msg = bindings.get(rule.head[1]) if len(rule.head) > 1 else None
                reason = str(msg) if msg else "Rego deny rule fired"
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=reason,
                    policy_id=self._policy_id,
                )

        # Pass 2: require_approval overrides allow when no approval
        # was supplied.
        for rule in self._module.rules:
            if rule.head[0] != "require_approval":
                continue
            bindings = {}
            if _all_body_exprs_true(rule, bindings, input_doc):
                msg = bindings.get(rule.head[1]) if len(rule.head) > 1 else None
                reason = str(msg) if msg else "Rego require_approval rule fired"
                if context.approval_granted and context.approval_ticket:
                    # Caller supplied an approval — let the allow pass
                    # below speak. We return None-equivalent by
                    # continuing; the decision flows to the allow pass.
                    continue
                return PolicyResult(
                    decision=PolicyDecision.REQUIRE_APPROVAL,
                    reason=reason,
                    policy_id=self._policy_id,
                )

        # Pass 3: allow rules.
        default_allow = _resolve_default(self._module, "allow", False)
        for rule in self._module.rules:
            if rule.head[0] != "allow":
                continue
            bindings = {}
            if _all_body_exprs_true(rule, bindings, input_doc):
                return PolicyResult(
                    decision=PolicyDecision.ALLOW,
                    reason="Rego allow rule fired",
                    policy_id=self._policy_id,
                )

        if default_allow:
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="Rego default allow",
                policy_id=self._policy_id,
            )
        return PolicyResult(
            decision=PolicyDecision.DEFER,
            reason="No Rego allow/deny rule fired",
            policy_id=self._policy_id,
        )

    def get_policy_id(self) -> str:
        return self._policy_id

    def get_policy_version(self) -> str:
        return self._version


def _all_body_exprs_true(
    rule: _Rule, bindings: dict[str, Any], input_doc: dict[str, Any]
) -> bool:
    for expr in rule.body:
        try:
            if not _eval_expression(expr, bindings, input_doc):
                return False
        except Exception:
            logger.warning(
                "Rego expression failed; treating rule as not-fired",
                exc_info=True,
            )
            return False
    return True


def _resolve_default(module: _Module, rule_name: str, fallback: Any) -> Any:
    for rule in module.rules:
        if rule.head and rule.head[0] == "default" and rule.head[1] == rule_name:
            return rule.head[2]
    return fallback


# ── OPA HTTP adapter ───────────────────────────────────────────────


class OPAHttpRegoPolicy:
    """Adapter that evaluates Rego against an external OPA HTTP API.

    Operators who already run OPA as a sidecar or cluster service can
    use this provider to get full Rego semantics (including features
    the built-in subset skips). The adapter POSTs ``{"input": {...}}``
    to ``<base_url>/v1/data/<package_path>`` and expects a response of
    the form::

        {"result": {"allow": bool, "deny": ["reason", ...],
                    "require_approval": ["reason", ...]}}

    Every call times out after ``timeout_seconds``; failures
    fail-closed to DENY so a sidecar outage can't accidentally open
    up access. The adapter uses stdlib ``urllib`` so SecureMCP doesn't
    take a new dep just to talk to OPA.

    Args:
        base_url: OPA service base URL (e.g. ``http://localhost:8181``).
        package_path: Slash-joined OPA package (e.g. ``securemcp/capability``).
        policy_id: Stable id surfaced in results.
        version: Version tag.
        timeout_seconds: HTTP timeout for each evaluation.
        transport: Optional override used by tests — a callable
            ``(url, body) -> dict`` that mimics the OPA HTTP response.
    """

    def __init__(
        self,
        *,
        base_url: str,
        package_path: str,
        policy_id: str = "opa-http",
        version: str = "1.0.0",
        timeout_seconds: float = 2.0,
        transport: Any = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._package_path = package_path.strip("/").replace(".", "/")
        self._policy_id = policy_id
        self._version = version
        self._timeout = timeout_seconds
        self._transport = transport

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        url = f"{self._base_url}/v1/data/{self._package_path}"
        body = {"input": _context_to_input(context)}
        try:
            payload = self._send(url, body)
        except Exception as exc:
            logger.warning("OPA evaluation failed: %s", exc)
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"OPA unreachable (fail-closed): {exc}",
                policy_id=self._policy_id,
            )
        result = (payload or {}).get("result") or {}
        deny_reasons = result.get("deny") or []
        if deny_reasons:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=_first_msg(deny_reasons, "OPA deny"),
                policy_id=self._policy_id,
            )
        approval_reasons = result.get("require_approval") or []
        if approval_reasons and not (
            context.approval_granted and context.approval_ticket
        ):
            return PolicyResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                reason=_first_msg(approval_reasons, "OPA require_approval"),
                policy_id=self._policy_id,
            )
        if result.get("allow"):
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="OPA allow",
                policy_id=self._policy_id,
            )
        return PolicyResult(
            decision=PolicyDecision.DEFER,
            reason="OPA returned no allow/deny",
            policy_id=self._policy_id,
        )

    def get_policy_id(self) -> str:
        return self._policy_id

    def get_policy_version(self) -> str:
        return self._version

    def _send(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(url, body)
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def _first_msg(values: list[Any], fallback: str) -> str:
    for v in values:
        if isinstance(v, str) and v:
            return v
    return fallback

"""OpenAPI tool executor (Iter 13.3).

The executor turns a detailed operation surface produced by
:func:`purecipher.openapi_store.extract_openapi_operations_detailed`
into an outgoing HTTP request. It runs in three stages:

* **Argument assembly** (this iter): split a structured ``args`` dict
  into path / query / header / cookie / body pieces, URL-encode each
  according to OpenAPI defaults, and produce a request blueprint.
* **Credential application** (Iter 13.3.2): pick the right credential
  out of the publisher's store, write it into the request.
* **Execution** (Iter 13.3.3): validate the assembled args against
  ``input_schema``, fire the HTTP call through ``httpx``, and surface
  a structured ``ExecutorResult``.

The blueprint is deliberately a plain dataclass — no ``httpx`` types
leak out of the builder so the URL/encoding logic is pure and unit
testable without a network mock.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from purecipher.openapi_store import (
    OpenAPICredentialRecord,
    OpenAPIOperationDetailed,
    OpenAPIParameter,
    OpenAPIStore,
    SecurityRequirement,
    SecurityScheme,
    extract_security_schemes,
    resolve_operation_security,
)

logger = logging.getLogger(__name__)


_DEFAULT_QUERY_STYLE = "form"
_DEFAULT_PATH_STYLE = "simple"
_DEFAULT_HEADER_STYLE = "simple"
_DEFAULT_COOKIE_STYLE = "form"


@dataclass
class RequestBlueprint:
    """Pure-data description of an outgoing request.

    The credential layer (Iter 13.3.2) mutates this in place; the
    execute layer (Iter 13.3.3) hands it to ``httpx``. Keeping it free
    of HTTP-client types lets the request-building logic be exercised
    in isolation.
    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: list[tuple[str, str]] = field(default_factory=list)
    cookies: dict[str, str] = field(default_factory=dict)
    body: Any | None = None
    content_type: str | None = None


# ---------------------------------------------------------------------------
# Encoding helpers (RFC 3986 + OpenAPI 3 defaults)
# ---------------------------------------------------------------------------


def _stringify(value: Any) -> str:
    """Coerce a primitive to its OpenAPI wire form.

    Booleans must be lowercase (``true``/``false``) per OpenAPI's JSON
    Schema lineage; ``None`` becomes the empty string so consumers
    don't see the literal string ``"None"`` on the wire.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _encode_path_value(value: Any) -> str:
    """Path-style encoding: percent-encode reserved chars including ``/``.

    Per OpenAPI default ``style: simple, explode: false``, list/object
    values are joined with commas.
    """
    if isinstance(value, list):
        joined = ",".join(_stringify(item) for item in value)
        return quote(joined, safe="")
    if isinstance(value, dict):
        # OpenAPI "simple" style for objects: ``key,value,key,value``
        parts: list[str] = []
        for k, v in value.items():
            parts.append(_stringify(k))
            parts.append(_stringify(v))
        return quote(",".join(parts), safe="")
    return quote(_stringify(value), safe="")


def _encode_query_pairs(
    name: str, value: Any, *, explode: bool
) -> list[tuple[str, str]]:
    """Query-style ``form`` encoding.

    Default for OpenAPI 3 is ``style: form, explode: true``. Lists
    repeat the parameter (``?tag=a&tag=b``) when exploded, comma-join
    when collapsed. Objects explode into key/value pairs of their own.
    """
    if isinstance(value, list):
        if explode:
            return [(name, _stringify(item)) for item in value]
        return [(name, ",".join(_stringify(item) for item in value))]
    if isinstance(value, dict):
        if explode:
            return [(_stringify(k), _stringify(v)) for k, v in value.items()]
        joined = ",".join(f"{_stringify(k)},{_stringify(v)}" for k, v in value.items())
        return [(name, joined)]
    return [(name, _stringify(value))]


def _encode_header_value(value: Any) -> str:
    """Header-style ``simple`` encoding (always non-exploded for arrays)."""
    if isinstance(value, list):
        return ",".join(_stringify(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for k, v in value.items():
            parts.append(_stringify(k))
            parts.append(_stringify(v))
        return ",".join(parts)
    return _stringify(value)


def _interpolate_path(path: str, path_args: dict[str, Any]) -> str:
    """Replace each ``{name}`` token with the URL-encoded path value.

    Tokens not present in ``path_args`` are left as-is so the caller's
    schema validator (Iter 13.3.3) flags them as missing-required —
    the executor never invents a placeholder.
    """
    out = path
    for token, raw in path_args.items():
        encoded = _encode_path_value(raw)
        out = out.replace("{" + token + "}", encoded)
    return out


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


@dataclass
class OpenAPIToolExecutor:
    """Build (and later execute) an OpenAPI operation invocation."""

    spec: dict[str, Any]
    operation: OpenAPIOperationDetailed
    server_url: str
    publisher_id: str = ""
    source_id: str = ""

    def build_request(self, args: dict[str, Any]) -> RequestBlueprint:
        """Assemble a :class:`RequestBlueprint` from structured args.

        ``args`` mirrors the operation's ``input_schema`` shape::

            {
              "path":   {"petId": 7},
              "query":  {"limit": 10, "tags": ["a", "b"]},
              "header": {"X-Trace-Id": "abc"},
              "cookie": {"session": "…"},
              "body":   {"name": "Fido"}
            }

        Sections that are absent simply contribute nothing to the
        request. No validation happens here — that's
        :meth:`validate_arguments` in Iter 13.3.3.
        """
        if not isinstance(args, dict):
            raise ValueError("args must be a dict matching the operation input_schema")

        path_args: dict[str, Any] = (
            args.get("path") if isinstance(args.get("path"), dict) else {}
        ) or {}
        query_args: dict[str, Any] = (
            args.get("query") if isinstance(args.get("query"), dict) else {}
        ) or {}
        header_args: dict[str, Any] = (
            args.get("header") if isinstance(args.get("header"), dict) else {}
        ) or {}
        cookie_args: dict[str, Any] = (
            args.get("cookie") if isinstance(args.get("cookie"), dict) else {}
        ) or {}
        body_arg: Any = args.get("body")

        path = self.operation.get("path", "")
        method = str(self.operation.get("method", "get")).upper()

        # Build URL: server_url + interpolated path. Trim trailing slash
        # on the server so we don't accidentally emit a double slash.
        base = self.server_url.rstrip("/")
        rendered_path = _interpolate_path(path, path_args)
        url = f"{base}{rendered_path}"

        # Index parameter metadata once so we can look up explode/style.
        params_by_key: dict[tuple[str, str], OpenAPIParameter] = {}
        for param in self.operation.get("parameters", []) or []:
            key = (str(param.get("name") or ""), str(param.get("location") or ""))
            params_by_key[key] = param

        # Query params (default form/explode=true).
        query_pairs: list[tuple[str, str]] = []
        for q_name, q_value in query_args.items():
            param_meta = params_by_key.get((q_name, "query")) or {}
            explode = bool(param_meta.get("explode", True))
            query_pairs.extend(_encode_query_pairs(q_name, q_value, explode=explode))

        # Header params (default simple, never explode for arrays).
        headers: dict[str, str] = {}
        for h_name, h_value in header_args.items():
            headers[h_name] = _encode_header_value(h_value)

        # Cookie params (default form). Cookies are key/value, joined by "; "
        cookies: dict[str, str] = {}
        for c_name, c_value in cookie_args.items():
            cookies[c_name] = _stringify(c_value)

        # Body — content type from the operation's request_body if it
        # carries one, else None (no body).
        body: Any | None = None
        content_type: str | None = None
        request_body = self.operation.get("request_body")
        if request_body is not None and body_arg is not None:
            content_type = request_body.get("content_type") or "application/json"
            body = body_arg

        return RequestBlueprint(
            method=method,
            url=url,
            headers=headers,
            query=query_pairs,
            cookies=cookies,
            body=body,
            content_type=content_type,
        )

    # ------------------------------------------------------------------
    # Credential layer (Iter 13.3.2)
    # ------------------------------------------------------------------

    def pick_credential_alternative(
        self, store: OpenAPIStore
    ) -> list[tuple[SecurityRequirement, OpenAPICredentialRecord]] | None:
        """Pick the first satisfiable security alternative for the
        operation against the publisher's credential store.

        Returns the matched ``(requirement, credential)`` pairs for
        every scheme in the chosen alternative, or:

        * ``[]`` — the operation requires no auth (empty security).
        * ``None`` — the operation requires auth, but no alternative
          can be satisfied with the credentials we have on hand.

        OpenAPI semantics: outer security alternatives are OR'd, inner
        scheme entries are AND'd. We pick the first OR alternative
        whose ANDed schemes are all backed by stored credentials.
        """
        scheme_map = extract_security_schemes(self.spec)
        operation_security = self.operation.get("security") or []
        alternatives = resolve_operation_security(operation_security, scheme_map)
        if not alternatives:
            # `security: []` at the operation level (or no global
            # requirement) — public endpoint, no credentials needed.
            return []

        for alternative in alternatives:
            matched: list[tuple[SecurityRequirement, OpenAPICredentialRecord]] = []
            satisfied = True
            for requirement in alternative:
                scheme_name = requirement.get("scheme_name") or ""
                # Cross-publisher isolation is enforced by the store —
                # we always pass our publisher_id.
                cred_id = OpenAPIStore._credential_id(
                    self.publisher_id, self.source_id, scheme_name
                )
                cred = store.get_credential(cred_id, publisher_id=self.publisher_id)
                if cred is None:
                    satisfied = False
                    break
                matched.append((requirement, cred))
            if satisfied:
                return matched
        return None

    def apply_credential(
        self,
        blueprint: RequestBlueprint,
        scheme: SecurityScheme,
        secret: dict[str, Any],
    ) -> None:
        """Mutate ``blueprint`` to carry credential material.

        Each kind writes to its canonical location:

        * ``apiKey`` — header / query / cookie per ``in``.
        * ``http`` ``bearer`` — ``Authorization: Bearer <token>``.
        * ``http`` ``basic`` — ``Authorization: Basic <b64(user:pass)>``.
        * ``oauth2`` — ``Authorization: Bearer <access_token>``.
        * ``openIdConnect`` — ``Authorization: Bearer <id_or_access>``.

        Schemes whose credentials are incomplete (e.g. ``oauth2`` with
        only a ``client_id`` and no token) raise ``ValueError`` rather
        than silently emit an unsigned request — surfacing the bug at
        invocation time is preferable to upstream returning ``401``.
        """
        kind = scheme.get("kind")
        if kind == "apiKey":
            api_key = str(secret.get("api_key") or "")
            if not api_key:
                raise ValueError("apiKey credential is missing `api_key`")
            api_in = str(scheme.get("api_key_in") or "")
            api_name = str(scheme.get("api_key_name") or "")
            if not api_name or api_in not in {"header", "query", "cookie"}:
                raise ValueError("apiKey scheme is malformed (missing name/in)")
            if api_in == "header":
                blueprint.headers[api_name] = api_key
            elif api_in == "query":
                blueprint.query.append((api_name, api_key))
            else:  # cookie
                blueprint.cookies[api_name] = api_key
            return

        if kind == "http":
            http_scheme = str(scheme.get("http_scheme") or "").lower()
            if http_scheme == "bearer":
                token = str(secret.get("bearer_token") or "")
                if not token:
                    raise ValueError("http bearer credential missing `bearer_token`")
                blueprint.headers["Authorization"] = f"Bearer {token}"
                return
            if http_scheme == "basic":
                user = str(secret.get("username") or "")
                pw = str(secret.get("password") or "")
                if not user:
                    raise ValueError("http basic credential missing `username`")
                encoded = base64.b64encode(f"{user}:{pw}".encode()).decode("ascii")
                blueprint.headers["Authorization"] = f"Basic {encoded}"
                return
            raise ValueError(
                f"Unsupported http scheme {http_scheme!r} (only bearer/basic)"
            )

        if kind == "oauth2":
            token = str(secret.get("access_token") or "")
            if not token:
                # Iter 13.3 ships with manually-provided access tokens.
                # Full OAuth2 flows (token exchange) are out of scope —
                # surface this clearly so callers know they need to
                # exchange before invoking.
                raise ValueError(
                    "oauth2 credential missing `access_token` "
                    "(token exchange is not implemented yet)"
                )
            blueprint.headers["Authorization"] = f"Bearer {token}"
            return

        if kind == "openIdConnect":
            token = str(secret.get("id_token") or secret.get("access_token") or "")
            if not token:
                raise ValueError(
                    "openIdConnect credential missing `id_token` or `access_token`"
                )
            blueprint.headers["Authorization"] = f"Bearer {token}"
            return

        if kind == "mutualTLS":
            # Client certs are out of scope for the in-process
            # executor — flag clearly so the caller routes through a
            # cert-aware path.
            raise ValueError(
                "mutualTLS schemes are not supported by the in-process executor"
            )

        raise ValueError(f"Unknown securityScheme kind {kind!r}")

    def apply_credentials_from_store(
        self, blueprint: RequestBlueprint, store: OpenAPIStore
    ) -> None:
        """Resolve + apply credentials in one shot.

        Raises ``RuntimeError`` if the operation requires auth and we
        have no satisfiable alternative on hand. The exception message
        names every scheme the publisher needs to register so the UI
        can surface a precise next action.
        """
        chosen = self.pick_credential_alternative(store)
        if chosen is None:
            scheme_map = extract_security_schemes(self.spec)
            alternatives = resolve_operation_security(
                self.operation.get("security") or [], scheme_map
            )
            wanted: list[str] = [
                " + ".join(req.get("scheme_name", "?") for req in alt)
                for alt in alternatives
            ]
            raise RuntimeError(
                "No credentials registered for operation "
                f"{self.operation.get('operation_key')!r}. "
                f"Need one of: {' OR '.join(wanted) if wanted else '(none)'}"
            )
        for requirement, credential in chosen:
            scheme = requirement.get("scheme")
            if scheme is None:
                # The store has a credential for this scheme name, but
                # the spec no longer declares it — surface as a
                # configuration drift rather than silently send an
                # unauthorised request.
                raise RuntimeError(
                    f"Credential references unknown scheme "
                    f"{requirement.get('scheme_name')!r}"
                )
            self.apply_credential(blueprint, scheme, credential.get("secret") or {})

    # ------------------------------------------------------------------
    # Validation + execution (Iter 13.3.3)
    # ------------------------------------------------------------------

    def validate_arguments(self, args: dict[str, Any]) -> None:
        """Validate ``args`` against the operation's ``input_schema``.

        Raises :class:`ArgumentValidationError` with a list of human-
        readable issues if the args don't match. ``jsonschema`` is
        used as the underlying engine — we ask for *all* errors via
        ``iter_errors`` so the UI can surface every problem at once
        rather than the first.
        """
        from jsonschema import Draft202012Validator

        input_schema = self.operation.get("input_schema") or {}
        validator = Draft202012Validator(input_schema)
        errors = sorted(
            validator.iter_errors(args), key=lambda e: list(e.absolute_path)
        )
        if not errors:
            return
        messages: list[str] = []
        for err in errors:
            location = ".".join(str(p) for p in err.absolute_path) or "(root)"
            messages.append(f"{location}: {err.message}")
        raise ArgumentValidationError(messages)

    async def execute(
        self,
        args: dict[str, Any],
        store: OpenAPIStore | None = None,
        *,
        timeout_seconds: float = 15.0,
        validate_input: bool = True,
        validate_output: bool = True,
        client: Any | None = None,
    ) -> ExecutorResult:
        """Run the operation end-to-end.

        Steps in order: validate args, build the blueprint, apply
        credentials (when a store is provided), send via ``httpx``,
        parse the response, and best-effort validate the parsed body
        against the output schema (warnings only — real APIs deviate).

        ``client`` lets tests inject an :class:`httpx.AsyncClient`
        backed by ``MockTransport`` so we don't need real network. When
        ``client`` is ``None`` we open a one-shot client scoped to the
        call.
        """
        import httpx

        if validate_input:
            self.validate_arguments(args)

        blueprint = self.build_request(args)
        if store is not None:
            self.apply_credentials_from_store(blueprint, store)

        # Build httpx request kwargs
        body_kwargs: dict[str, Any] = {}
        if blueprint.body is not None:
            ct = (blueprint.content_type or "").lower()
            if "json" in ct:
                body_kwargs["content"] = json.dumps(blueprint.body).encode("utf-8")
                # httpx will not re-set CT if we use ``content``, so do it.
                blueprint.headers.setdefault(
                    "Content-Type", blueprint.content_type or "application/json"
                )
            elif "form" in ct or "x-www-form-urlencoded" in ct:
                body_kwargs["data"] = blueprint.body
            else:
                # Octet-stream / text — pass raw bytes if possible.
                if isinstance(blueprint.body, (bytes, bytearray)):
                    body_kwargs["content"] = bytes(blueprint.body)
                elif isinstance(blueprint.body, str):
                    body_kwargs["content"] = blueprint.body.encode("utf-8")
                else:
                    body_kwargs["content"] = json.dumps(blueprint.body).encode("utf-8")

        request = httpx.Request(
            method=blueprint.method,
            url=blueprint.url,
            params=blueprint.query or None,
            headers=blueprint.headers or None,
            cookies=blueprint.cookies or None,
            **body_kwargs,
        )

        owns_client = client is None
        active_client: httpx.AsyncClient = (
            client if client is not None else httpx.AsyncClient(timeout=timeout_seconds)
        )
        try:
            response = await active_client.send(request)
        finally:
            if owns_client:
                await active_client.aclose()

        # Parse the body. We prefer JSON when the content-type advertises
        # it (or even when it doesn't but the body looks like JSON),
        # falling back to text. Binary payloads land in ``raw_bytes``.
        response_ct = response.headers.get("content-type", "").lower()
        parsed_body: Any = None
        raw_bytes: bytes | None = None
        if "json" in response_ct:
            try:
                parsed_body = response.json()
            except ValueError:
                parsed_body = response.text
        elif response_ct.startswith("text/") or response_ct == "":
            text = response.text
            # Be forgiving: if the upstream forgot to set CT but
            # returned valid JSON, try to decode it anyway.
            stripped = text.strip()
            if stripped and stripped[0] in "{[":
                try:
                    parsed_body = json.loads(text)
                except ValueError:
                    parsed_body = text
            else:
                parsed_body = text
        else:
            raw_bytes = response.content
            parsed_body = None

        result = ExecutorResult(
            status_code=response.status_code,
            headers=dict(response.headers),
            content_type=response_ct or None,
            body=parsed_body,
            raw_bytes=raw_bytes,
            validation_warnings=[],
        )

        if validate_output and 200 <= response.status_code < 300:
            output_schema = self.operation.get("output_schema")
            if output_schema and parsed_body is not None:
                from jsonschema import Draft202012Validator

                validator = Draft202012Validator(output_schema)
                for err in validator.iter_errors(parsed_body):
                    location = ".".join(str(p) for p in err.absolute_path) or "(root)"
                    msg = f"{location}: {err.message}"
                    logger.warning(
                        "OpenAPI executor output mismatch on %s %s — %s",
                        blueprint.method,
                        blueprint.url,
                        msg,
                    )
                    result.validation_warnings.append(msg)

        return result


@dataclass
class ExecutorResult:
    """Structured outcome of an OpenAPI invocation.

    The body is whatever we could parse from the upstream response —
    parsed JSON when the content-type indicated it (or the body looked
    like JSON anyway), text for ``text/*``, ``None`` for binary
    payloads (in which case ``raw_bytes`` carries the unmodified
    bytes). Output-schema mismatches are emitted as
    ``validation_warnings`` rather than raised so a flaky upstream
    doesn't break callers; the route layer surfaces them in the JSON
    response so the publisher can see them in the registry UI.
    """

    status_code: int
    headers: dict[str, str]
    content_type: str | None
    body: Any
    raw_bytes: bytes | None
    validation_warnings: list[str]


class ArgumentValidationError(Exception):
    """Raised when an invocation's arguments don't match input_schema.

    Carries a list of human-readable error messages — the route layer
    surfaces them as a 400 response so the caller sees every issue at
    once.
    """

    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = list(messages)

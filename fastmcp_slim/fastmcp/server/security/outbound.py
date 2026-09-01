"""Hardened outbound HTTP primitives for SecureMCP control planes."""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx2

from fastmcp.server.auth.ssrf import format_ip_for_url, is_ip_allowed

DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024

AddressResolver = Callable[[str, int], Iterable[tuple[Any, ...]]]
SyncTransportFactory = Callable[[], httpx2.BaseTransport]
AsyncTransportFactory = Callable[[], httpx2.AsyncBaseTransport]


class UnsafeOutboundURLError(ValueError):
    """Raised when an outbound target violates the configured network policy."""


class OutboundRequestError(RuntimeError):
    """Raised when a validated outbound request cannot complete safely."""


class OutboundResponseTooLargeError(OutboundRequestError):
    """Raised when an outbound response exceeds its byte budget."""


@dataclass(frozen=True)
class ValidatedOutboundURL:
    """An outbound URL whose hostname resolved only to approved addresses."""

    original_url: str
    scheme: str
    hostname: str
    port: int
    path: str
    query: str
    host_header: str
    resolved_addresses: tuple[str, ...]

    def connection_urls(self) -> tuple[str, ...]:
        """Return IP-pinned URLs for connection attempts."""
        return tuple(
            urlunsplit(
                (
                    self.scheme,
                    _address_netloc(address, self.port),
                    self.path,
                    self.query,
                    "",
                )
            )
            for address in self.resolved_addresses
        )


class OutboundNetworkPolicy:
    """Validate outbound destinations and pin their resolved addresses.

    HTTPS and globally routable unicast destinations are required by default.
    Local development exceptions are exact-host allowlists: cleartext HTTP and
    protected addresses are controlled independently, so allowing one never
    silently enables the other.
    """

    def __init__(
        self,
        *,
        allow_http_hosts: Iterable[str] = (),
        allow_private_hosts: Iterable[str] = (),
        resolver: AddressResolver = socket.getaddrinfo,
    ) -> None:
        self.allow_http_hosts = _normalize_hosts(allow_http_hosts)
        self.allow_private_hosts = _normalize_hosts(allow_private_hosts)
        self._resolver = resolver

    def resolve(self, url: str) -> ValidatedOutboundURL:
        """Validate ``url`` and resolve it once for the eventual connection."""
        parsed = _parse_outbound_url(url)
        hostname = _normalize_host(parsed.hostname or "")
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and hostname in self.allow_http_hosts
        ):
            raise UnsafeOutboundURLError(
                "Outbound destinations must use HTTPS unless their exact host "
                "is explicitly allowed for HTTP"
            )

        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise UnsafeOutboundURLError(
                "Outbound URL contains an invalid port"
            ) from exc

        addresses = self._resolve_addresses(hostname, port)
        if hostname not in self.allow_private_hosts:
            blocked = [address for address in addresses if not is_ip_allowed(address)]
            if blocked:
                raise UnsafeOutboundURLError(
                    f"Outbound host {hostname!r} resolves to a protected address"
                )

        return ValidatedOutboundURL(
            original_url=url,
            scheme=parsed.scheme,
            hostname=hostname,
            port=port,
            path=parsed.path or "/",
            query=parsed.query,
            host_header=_host_header(hostname, parsed, port),
            resolved_addresses=addresses,
        )

    def _resolve_addresses(self, hostname: str, port: int) -> tuple[str, ...]:
        try:
            entries = list(self._resolver(hostname, port))
        except OSError as exc:
            raise UnsafeOutboundURLError(
                f"Could not resolve outbound host {hostname!r}"
            ) from exc
        if not entries:
            raise UnsafeOutboundURLError(
                f"Could not resolve outbound host {hostname!r}"
            )

        addresses: list[str] = []
        for entry in entries:
            try:
                address = str(entry[4][0])
            except (IndexError, TypeError) as exc:
                raise UnsafeOutboundURLError(
                    f"Resolver returned an invalid address for {hostname!r}"
                ) from exc
            normalized = _normalize_ip(address, hostname)
            if normalized not in addresses:
                addresses.append(normalized)
        return tuple(addresses)


@dataclass(frozen=True)
class OutboundHTTPResponse:
    """Bounded response returned by the hardened request helpers."""

    status_code: int
    headers: dict[str, str]
    content: bytes


def secure_outbound_request(
    url: str,
    *,
    method: str,
    content: bytes,
    headers: Mapping[str, str] | None = None,
    policy: OutboundNetworkPolicy | None = None,
    timeout: float = 5.0,
    overall_timeout: float | None = None,
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    transport_factory: SyncTransportFactory | None = None,
) -> OutboundHTTPResponse:
    """Send one DNS-pinned request without redirects or environment proxies."""
    _validate_request_limits(
        content,
        timeout=timeout,
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
    )
    validated = (policy or OutboundNetworkPolicy()).resolve(url)
    deadline = time.monotonic() + _overall_timeout(overall_timeout, timeout)
    request_headers = _request_headers(headers, validated.host_header)
    transport = (
        transport_factory()
        if transport_factory is not None
        else httpx2.HTTPTransport(trust_env=False, retries=0)
    )
    last_connect_error: Exception | None = None

    with httpx2.Client(
        transport=transport,
        timeout=_timeout(timeout),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for target_url in validated.connection_urls():
            _ensure_before_deadline(deadline)
            try:
                with client.stream(
                    method,
                    target_url,
                    content=content,
                    headers=request_headers,
                    extensions={"sni_hostname": validated.hostname},
                ) as response:
                    return _consume_response(
                        response,
                        hostname=validated.hostname,
                        deadline=deadline,
                        max_response_bytes=max_response_bytes,
                    )
            except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
                last_connect_error = exc

    raise OutboundRequestError(
        f"Could not connect to outbound host {validated.hostname!r}"
    ) from last_connect_error


async def async_secure_outbound_request(
    url: str,
    *,
    method: str,
    content: bytes,
    headers: Mapping[str, str] | None = None,
    policy: OutboundNetworkPolicy | None = None,
    timeout: float = 5.0,
    overall_timeout: float | None = None,
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    transport_factory: AsyncTransportFactory | None = None,
) -> OutboundHTTPResponse:
    """Async counterpart to :func:`secure_outbound_request`."""
    _validate_request_limits(
        content,
        timeout=timeout,
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
    )
    resolved_policy = policy or OutboundNetworkPolicy()
    validated = await asyncio.to_thread(resolved_policy.resolve, url)
    deadline = time.monotonic() + _overall_timeout(overall_timeout, timeout)
    request_headers = _request_headers(headers, validated.host_header)
    transport = (
        transport_factory()
        if transport_factory is not None
        else httpx2.AsyncHTTPTransport(trust_env=False, retries=0)
    )
    last_connect_error: Exception | None = None

    async with httpx2.AsyncClient(
        transport=transport,
        timeout=_timeout(timeout),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for target_url in validated.connection_urls():
            _ensure_before_deadline(deadline)
            try:
                async with client.stream(
                    method,
                    target_url,
                    content=content,
                    headers=request_headers,
                    extensions={"sni_hostname": validated.hostname},
                ) as response:
                    return await _consume_response_async(
                        response,
                        hostname=validated.hostname,
                        deadline=deadline,
                        max_response_bytes=max_response_bytes,
                    )
            except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
                last_connect_error = exc

    raise OutboundRequestError(
        f"Could not connect to outbound host {validated.hostname!r}"
    ) from last_connect_error


def _parse_outbound_url(url: str) -> SplitResult:
    if type(url) is not str or not url or any(char.isspace() for char in url):
        raise UnsafeOutboundURLError("Outbound URL must be a non-empty URL string")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except (ValueError, AttributeError) as exc:
        raise UnsafeOutboundURLError("Outbound URL is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise UnsafeOutboundURLError("Outbound URL must contain an HTTP(S) host")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeOutboundURLError("Outbound URL may not contain credentials")
    if parsed.fragment:
        raise UnsafeOutboundURLError("Outbound URL may not contain a fragment")
    return parsed


def _normalize_hosts(hosts: Iterable[str]) -> frozenset[str]:
    normalized: set[str] = set()
    for host in hosts:
        if type(host) is not str or not host.strip():
            raise ValueError("Outbound host exceptions must be non-empty strings")
        normalized.add(_normalize_host(host))
    return frozenset(normalized)


def _normalize_host(host: str) -> str:
    value = host.strip().rstrip(".").lower()
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeOutboundURLError(
            "Outbound URL contains an invalid hostname"
        ) from exc


def _normalize_ip(address: str, hostname: str) -> str:
    import ipaddress

    try:
        return str(ipaddress.ip_address(address))
    except ValueError as exc:
        raise UnsafeOutboundURLError(
            f"Resolver returned an invalid address for {hostname!r}"
        ) from exc


def _host_header(hostname: str, parsed: SplitResult, port: int) -> str:
    rendered_host = format_ip_for_url(hostname)
    default_port = 443 if parsed.scheme == "https" else 80
    return rendered_host if port == default_port else f"{rendered_host}:{port}"


def _address_netloc(address: str, port: int) -> str:
    return f"{format_ip_for_url(address)}:{port}"


def _request_headers(
    headers: Mapping[str, str] | None,
    host_header: str,
) -> dict[str, str]:
    result = {
        key: value for key, value in (headers or {}).items() if key.lower() != "host"
    }
    result["Host"] = host_header
    return result


def _timeout(timeout: float) -> httpx2.Timeout:
    return httpx2.Timeout(
        connect=timeout,
        read=timeout,
        write=timeout,
        pool=timeout,
    )


def _overall_timeout(configured: float | None, operation_timeout: float) -> float:
    value = operation_timeout if configured is None else configured
    if value <= 0:
        raise ValueError("overall_timeout must be greater than zero")
    return value


def _validate_request_limits(
    content: bytes,
    *,
    timeout: float,
    max_request_bytes: int,
    max_response_bytes: int,
) -> None:
    if type(content) is not bytes:
        raise TypeError("Outbound request content must be bytes")
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if max_request_bytes <= 0 or max_response_bytes <= 0:
        raise ValueError("Outbound byte limits must be greater than zero")
    if len(content) > max_request_bytes:
        raise OutboundRequestError(
            f"Outbound request exceeds the {max_request_bytes}-byte limit"
        )


def _ensure_before_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise OutboundRequestError("Outbound request exceeded its overall timeout")


def _declared_response_size(headers: Mapping[str, str]) -> int | None:
    raw_size = headers.get("content-length")
    if raw_size is None:
        return None
    try:
        size = int(raw_size)
    except ValueError:
        return None
    return size if size >= 0 else None


def _validate_response_status(status_code: int, hostname: str) -> None:
    if 300 <= status_code < 400:
        raise OutboundRequestError(
            f"Redirects from outbound host {hostname!r} are not allowed"
        )
    if not 200 <= status_code < 300:
        raise OutboundRequestError(
            f"Outbound host {hostname!r} returned HTTP {status_code}"
        )


def _consume_response(
    response: httpx2.Response,
    *,
    hostname: str,
    deadline: float,
    max_response_bytes: int,
) -> OutboundHTTPResponse:
    _validate_response_status(response.status_code, hostname)
    declared = _declared_response_size(response.headers)
    if declared is not None and declared > max_response_bytes:
        raise OutboundResponseTooLargeError(
            f"Outbound response exceeds the {max_response_bytes}-byte limit"
        )

    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        _ensure_before_deadline(deadline)
        size += len(chunk)
        if size > max_response_bytes:
            raise OutboundResponseTooLargeError(
                f"Outbound response exceeds the {max_response_bytes}-byte limit"
            )
        chunks.append(chunk)
    return OutboundHTTPResponse(
        status_code=response.status_code,
        headers=dict(response.headers),
        content=b"".join(chunks),
    )


async def _consume_response_async(
    response: httpx2.Response,
    *,
    hostname: str,
    deadline: float,
    max_response_bytes: int,
) -> OutboundHTTPResponse:
    _validate_response_status(response.status_code, hostname)
    declared = _declared_response_size(response.headers)
    if declared is not None and declared > max_response_bytes:
        raise OutboundResponseTooLargeError(
            f"Outbound response exceeds the {max_response_bytes}-byte limit"
        )

    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        _ensure_before_deadline(deadline)
        size += len(chunk)
        if size > max_response_bytes:
            raise OutboundResponseTooLargeError(
                f"Outbound response exceeds the {max_response_bytes}-byte limit"
            )
        chunks.append(chunk)
    return OutboundHTTPResponse(
        status_code=response.status_code,
        headers=dict(response.headers),
        content=b"".join(chunks),
    )


__all__ = [
    "DEFAULT_MAX_REQUEST_BYTES",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "AddressResolver",
    "AsyncTransportFactory",
    "OutboundHTTPResponse",
    "OutboundNetworkPolicy",
    "OutboundRequestError",
    "OutboundResponseTooLargeError",
    "SyncTransportFactory",
    "UnsafeOutboundURLError",
    "ValidatedOutboundURL",
    "async_secure_outbound_request",
    "secure_outbound_request",
]

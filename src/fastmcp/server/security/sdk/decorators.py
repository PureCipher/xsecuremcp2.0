"""Security decorators for tool functions.

Wraps tool functions with runtime enforcement of trust, sandbox,
certification, permission, provenance, and policy-engine checks.

The decorator does two jobs:

1. **Registry** — stores a :class:`SecurityDecoratorConfig` per tool name.
   This is the long-standing role and works without a client attached.
2. **Enforcement** — when constructed with a :class:`SecureMCPClient`,
   instances are *callable*: ``@security("tool")`` returns a wrapped
   function that runs ``client.check_tool`` (or ``acheck_tool`` for async
   functions) before each invocation, denies via :class:`SecurityDenied`
   when the check fails, applies an optional async timeout, and records
   provenance afterwards.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastmcp.server.security.certification.manifest import (
    PermissionScope,
    SecurityManifest,
)

if TYPE_CHECKING:
    from fastmcp.server.security.sdk.client import (
        SecureMCPClient,
        SecurityCheckResult,
    )

logger = logging.getLogger(__name__)


# A manifest provider lets the caller materialize a per-tool SecurityManifest
# at decoration time without forcing a one-shot manifest at registration.
ManifestProvider = Callable[[str, "SecurityDecoratorConfig"], SecurityManifest | None]


class SecurityDenied(Exception):
    """Raised when a SecurityDecorator-wrapped tool is denied at call time.

    The originating :class:`SecurityCheckResult` is attached as ``.result``
    so callers can introspect why the call was rejected (revocation, low
    trust score, policy denial, sandbox block, missing certification, or
    missing required permissions).
    """

    def __init__(self, result: SecurityCheckResult) -> None:
        self.result = result
        reasons = "; ".join(result.reasons) if result.reasons else "unspecified"
        super().__init__(
            f"Security check denied tool '{result.tool_name}': {reasons}"
        )


@dataclass
class SecurityDecoratorConfig:
    """Configuration for a security decorator.

    Defines what security checks and recording should be applied to a
    decorated tool function.
    """

    config_id: str = ""
    tool_name: str = ""
    required_permissions: set[PermissionScope] = field(default_factory=set)
    min_trust_score: float = 0.0
    require_certification: bool = False
    record_provenance: bool = True
    sandbox_enabled: bool = False
    max_execution_seconds: float = 30.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.config_id:
            self.config_id = f"sdcfg-{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> dict:
        return {
            "config_id": self.config_id,
            "tool_name": self.tool_name,
            "required_permissions": [p.value for p in self.required_permissions],
            "min_trust_score": self.min_trust_score,
            "require_certification": self.require_certification,
            "record_provenance": self.record_provenance,
            "sandbox_enabled": self.sandbox_enabled,
            "max_execution_seconds": self.max_execution_seconds,
        }


@dataclass
class SecurityDecorator:
    """Applies security policies to tool functions at call time.

    When a :class:`SecureMCPClient` is attached, the decorator becomes a
    real wrapping decorator that enforces every configured rule before
    the wrapped function runs and records provenance afterwards. Without
    a client the decorator still acts as a registry (back-compat); a
    runtime ``RuntimeError`` is raised the first time an attempt is made
    to invoke an enforcement-wrapped function without a client.

    Example::

        client = SecureMCPClient(policy_engine=engine, registry=reg, ...)
        security = SecurityDecorator(client=client)

        @security("get_weather", min_trust_score=0.5)
        async def get_weather(city: str) -> str:
            ...

        @security  # bare-decorator form — uses fn.__name__
        def echo(text: str) -> str:
            return text
    """

    decorator_id: str = ""
    registered_tools: dict[str, SecurityDecoratorConfig] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Optional enforcement wiring. Typed loosely to avoid a circular import
    # between client.py and decorators.py.
    client: Any = None  # SecureMCPClient | None
    manifest_provider: Any = None  # ManifestProvider | None

    def __post_init__(self) -> None:
        if not self.decorator_id:
            self.decorator_id = f"sd-{uuid.uuid4().hex[:8]}"

    # ── Registry surface (existing API) ──────────────────────────

    def register(
        self,
        tool_name: str,
        config: SecurityDecoratorConfig | None = None,
        **kwargs: Any,
    ) -> SecurityDecoratorConfig:
        """Register a tool with security configuration.

        Args:
            tool_name: Name of the tool.
            config: Pre-built config, or pass kwargs to build one.

        Returns:
            The registered SecurityDecoratorConfig.
        """
        if config is None:
            config = SecurityDecoratorConfig(tool_name=tool_name, **kwargs)
        else:
            config.tool_name = tool_name
        self.registered_tools[tool_name] = config
        return config

    def unregister(self, tool_name: str) -> bool:
        """Remove a tool registration."""
        if tool_name in self.registered_tools:
            del self.registered_tools[tool_name]
            return True
        return False

    def get_config(self, tool_name: str) -> SecurityDecoratorConfig | None:
        """Get the security config for a registered tool."""
        return self.registered_tools.get(tool_name)

    @property
    def tool_count(self) -> int:
        return len(self.registered_tools)

    def get_tools_requiring_certification(self) -> list[str]:
        """Get tools that require certification."""
        return [
            name
            for name, cfg in self.registered_tools.items()
            if cfg.require_certification
        ]

    def get_tools_with_sandbox(self) -> list[str]:
        """Get tools with sandbox enabled."""
        return [
            name for name, cfg in self.registered_tools.items() if cfg.sandbox_enabled
        ]

    def to_dict(self) -> dict:
        return {
            "decorator_id": self.decorator_id,
            "tool_count": self.tool_count,
            "client_attached": self.client is not None,
            "tools": {
                name: cfg.to_dict() for name, cfg in self.registered_tools.items()
            },
        }

    # ── Enforcement surface (decoration) ─────────────────────────

    def __call__(
        self,
        tool_name: str | Callable[..., Any] | None = None,
        *,
        config: SecurityDecoratorConfig | None = None,
        **config_kwargs: Any,
    ) -> Callable[..., Any]:
        """Return a decorator that wraps a tool function with enforcement.

        Three calling conventions are supported::

            @security                    # bare; tool_name = fn.__name__
            def echo(...): ...

            @security("explicit_name")   # explicit tool name
            def echo(...): ...

            @security("name", min_trust_score=0.5, require_certification=True)
            def echo(...): ...

        Async functions are wrapped with an async wrapper that awaits
        ``client.acheck_tool``; sync functions get a sync wrapper that
        calls ``client.check_tool``.
        """
        # Bare form: @security applied directly to a function.
        if callable(tool_name) and config is None and not config_kwargs:
            fn = tool_name
            return self._wrap(fn, fn.__name__, None, {})

        # Parameterized form: @security(name, **kwargs) → returns a decorator.
        explicit_name = tool_name if isinstance(tool_name, str) else None

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return self._wrap(fn, explicit_name or fn.__name__, config, config_kwargs)

        return decorator

    def decorate(
        self,
        tool_name: str | None = None,
        *,
        config: SecurityDecoratorConfig | None = None,
        **config_kwargs: Any,
    ) -> Callable[..., Any]:
        """Explicit alias for :meth:`__call__` (parameterized form only)."""
        return self.__call__(tool_name, config=config, **config_kwargs)

    # ── Internals ───────────────────────────────────────────────

    def _wrap(
        self,
        fn: Callable[..., Any],
        tool_name: str,
        config: SecurityDecoratorConfig | None,
        config_kwargs: dict[str, Any],
    ) -> Callable[..., Any]:
        cfg = self.register(tool_name, config=config, **config_kwargs)

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                check = await self._enforce_async(tool_name, cfg)
                try:
                    if cfg.max_execution_seconds and cfg.max_execution_seconds > 0:
                        result = await asyncio.wait_for(
                            fn(*args, **kwargs),
                            timeout=cfg.max_execution_seconds,
                        )
                    else:
                        result = await fn(*args, **kwargs)
                except BaseException as exc:
                    self._record_failure(tool_name, cfg, args, kwargs, exc)
                    raise
                self._record_success(tool_name, cfg, args, kwargs, result, check)
                return result

            async_wrapper.__wrapped_security_config__ = cfg  # type: ignore[attr-defined]
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            check = self._enforce_sync(tool_name, cfg)
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                self._record_failure(tool_name, cfg, args, kwargs, exc)
                raise
            self._record_success(tool_name, cfg, args, kwargs, result, check)
            return result

        sync_wrapper.__wrapped_security_config__ = cfg  # type: ignore[attr-defined]
        return sync_wrapper

    def _require_client(self) -> None:
        if self.client is None:
            raise RuntimeError(
                f"SecurityDecorator '{self.decorator_id}' has no client attached "
                "and cannot enforce security checks at call time. Construct it "
                "as SecurityDecorator(client=SecureMCPClient(...)) to enable "
                "enforcement, or use it purely as a configuration registry."
            )

    def _build_manifest(
        self, tool_name: str, cfg: SecurityDecoratorConfig
    ) -> SecurityManifest | None:
        if self.manifest_provider is None:
            return None
        try:
            return self.manifest_provider(tool_name, cfg)
        except Exception:
            logger.warning(
                "manifest_provider raised for tool '%s'; sandbox disabled "
                "for this call",
                tool_name,
                exc_info=True,
            )
            return None

    @staticmethod
    def _manifest_permissions(
        manifest: SecurityManifest | None,
    ) -> set[PermissionScope]:
        if manifest is None:
            return set()
        raw: Iterable[PermissionScope] | None = getattr(manifest, "permissions", None)
        if not raw:
            return set()
        return set(raw)

    def _post_check(
        self,
        tool_name: str,
        cfg: SecurityDecoratorConfig,
        result: SecurityCheckResult,
        manifest: SecurityManifest | None,
    ) -> SecurityCheckResult:
        """Apply decorator-level rules on top of ``client.check_tool``.

        These add to the SDK's signal:
        - ``require_certification`` is enforced here (the SDK records the
          state but does not gate on it).
        - ``required_permissions`` is verified against the manifest's
          declared permission grant. If no manifest is available the call
          is denied — required permissions cannot be satisfied without one.
        """
        if cfg.require_certification and not result.is_certified:
            result.allowed = False
            result.reasons.append(
                f"Tool '{tool_name}' requires certification (none on file)"
            )

        if cfg.required_permissions:
            granted = self._manifest_permissions(manifest)
            missing = [p for p in cfg.required_permissions if p not in granted]
            if missing:
                result.allowed = False
                missing_names = sorted(p.value for p in missing)
                granted_names = sorted(p.value for p in granted)
                result.reasons.append(
                    f"Tool '{tool_name}' missing required permissions "
                    f"{missing_names}; manifest grants {granted_names}"
                )
        return result

    def _enforce_sync(
        self, tool_name: str, cfg: SecurityDecoratorConfig
    ) -> SecurityCheckResult:
        self._require_client()
        manifest = (
            self._build_manifest(tool_name, cfg) if cfg.sandbox_enabled else None
        )
        result = self.client.check_tool(
            tool_name,
            min_trust_score=cfg.min_trust_score,
            manifest=manifest,
        )
        result = self._post_check(tool_name, cfg, result, manifest)
        if not result.allowed:
            raise SecurityDenied(result)
        return result

    async def _enforce_async(
        self, tool_name: str, cfg: SecurityDecoratorConfig
    ) -> SecurityCheckResult:
        self._require_client()
        manifest = (
            self._build_manifest(tool_name, cfg) if cfg.sandbox_enabled else None
        )
        result = await self.client.acheck_tool(
            tool_name,
            min_trust_score=cfg.min_trust_score,
            manifest=manifest,
        )
        result = self._post_check(tool_name, cfg, result, manifest)
        if not result.allowed:
            raise SecurityDenied(result)
        return result

    def _record_success(
        self,
        tool_name: str,
        cfg: SecurityDecoratorConfig,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        output: Any,
        check: SecurityCheckResult,
    ) -> None:
        if not cfg.record_provenance or self.client is None:
            return
        try:
            self.client.record_action(
                tool_name,
                "execute",
                metadata={
                    "args_count": len(args),
                    "kwargs_keys": sorted(kwargs.keys()),
                    "config_id": cfg.config_id,
                    "check_id": check.check_id,
                    "outcome": "success",
                },
            )
        except Exception:
            logger.warning(
                "Failed to record provenance for tool '%s'",
                tool_name,
                exc_info=True,
            )

    def _record_failure(
        self,
        tool_name: str,
        cfg: SecurityDecoratorConfig,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        exc: BaseException,
    ) -> None:
        if not cfg.record_provenance or self.client is None:
            return
        try:
            self.client.record_action(
                tool_name,
                "execution_error",
                metadata={
                    "args_count": len(args),
                    "kwargs_keys": sorted(kwargs.keys()),
                    "config_id": cfg.config_id,
                    "error_type": type(exc).__name__,
                    "outcome": "error",
                },
            )
        except Exception:
            logger.debug(
                "Failed to record provenance failure for tool '%s'",
                tool_name,
                exc_info=True,
            )

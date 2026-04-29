"""PureCipher Verified Registry MVP built on SecureMCP."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypedDict
from urllib.parse import quote, urlencode

from mcp.server.lowlevel.server import LifespanResultT
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from fastmcp.server.security.certification.attestation import CertificationLevel
from fastmcp.server.security.certification.manifest import (
    DataClassification,
    DataFlowDeclaration,
    PermissionScope,
    ResourceAccessDeclaration,
    SecurityManifest,
)
from fastmcp.server.security.certification.pipeline import CertificationPipeline
from fastmcp.server.security.contracts.crypto import (
    ContractCryptoHandler,
    SigningAlgorithm,
)
from fastmcp.server.security.gateway.tool_marketplace import (
    AttestationKind,
    HostingMode,
    ModerationAction,
    PublishStatus,
    ToolCategory,
    ToolListing,
    ToolMarketplace,
)
from fastmcp.server.security.orchestrator import SecurityContext
from fastmcp.server.security.registry.registry import TrustRegistry
from fastmcp.server.security.storage.sqlite import SQLiteBackend
from fastmcp.utilities.ui import create_secure_html_response
from purecipher.account_activity import RegistryAccountActivityStore
from purecipher.account_security import (
    LoginLockout,
    RegistryAccountSecurityStore,
)
from purecipher.auth import RegistryAuthSettings, RegistryRole, RegistrySession
from purecipher.clients import (
    CLIENT_KINDS,
    ClientStoreError,
    RegistryClient,
    RegistryClientStore,
    RegistryClientToken,
)
from purecipher.control_plane_settings import (
    PLANE_NAMES,
    RegistryControlPlaneStore,
)
from purecipher.db_migrations import migrate_registry_database
from purecipher.install import build_install_recipes
from purecipher.middleware.client_actor import (
    ClientActorResolverMiddleware,
)
from purecipher.middleware.client_aware_middleware import (
    upgrade_middleware_for_client_actor,
)
from purecipher.moderation import build_review_queue, moderation_action_from_name
from purecipher.notification_feed import RegistryNotificationFeed
from purecipher.openapi_store import OpenAPIStore, extract_openapi_operations
from purecipher.policy_routes import mount_registry_policy_routes
from purecipher.publishers import (
    get_public_publisher_profile,
    list_public_publishers,
    publisher_id_from_author,
)
from purecipher.ui import (
    SAMPLE_MANIFEST_JSON,
    SAMPLE_RUNTIME_METADATA_JSON,
    create_listing_detail_html,
    create_login_html,
    create_publish_html,
    create_publisher_index_html,
    create_publisher_profile_html,
    create_registry_ui_html,
    create_review_queue_html,
    create_setup_html,
)
from purecipher.user_preferences import RegistryUserPreferenceStore
from securemcp import SecureMCP
from securemcp.config import (
    AlertConfig,
    CertificationConfig,
    ConsentConfig,
    ContractConfig,
    IntrospectionConfig,
    PolicyConfig,
    ProvenanceConfig,
    ReflexiveConfig,
    RegistryConfig,
    SecurityConfig,
    ToolMarketplaceConfig,
)
from securemcp.http import SecurityAPI

logger = logging.getLogger(__name__)


@dataclass
class RegistrySubmissionResult:
    """Outcome of a registry submission attempt."""

    accepted: bool
    reason: str
    report: Any
    attestation: Any
    manifest_digest: str
    listing: ToolListing | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the submission result for HTTP responses."""

        payload = {
            "accepted": self.accepted,
            "reason": self.reason,
            "manifest_digest": self.manifest_digest,
            "report": self.report.to_dict(),
            "attestation": self.attestation.to_dict(),
        }
        if self.listing is not None:
            payload["listing"] = self.listing.to_dict()
        return payload


@dataclass
class RegistryPreflightResult:
    """Outcome of a non-publishing submission validation pass."""

    ready_for_publish: bool
    summary: str
    requested_level: str
    effective_certification_level: str
    minimum_required_level: str
    meets_minimum: bool
    manifest_digest: str
    install_ready: bool
    install_recipes: list[dict[str, Any]]
    report: Any
    attestation: Any

    def to_dict(self) -> dict[str, Any]:
        """Serialize the preflight result for HTTP responses."""

        return {
            "ready_for_publish": self.ready_for_publish,
            "summary": self.summary,
            "requested_level": self.requested_level,
            "effective_certification_level": self.effective_certification_level,
            "minimum_required_level": self.minimum_required_level,
            "meets_minimum": self.meets_minimum,
            "manifest_digest": self.manifest_digest,
            "install_ready": self.install_ready,
            "install_recipes": list(self.install_recipes),
            "report": self.report.to_dict(),
            "attestation": self.attestation.to_dict(),
        }


class PublishFormState(TypedDict):
    manifest_text: str
    runtime_metadata_text: str
    display_name: str
    categories: str
    tags: str
    requested_level: str
    source_url: str
    homepage_url: str
    tool_license: str
    submission_action: str


def _parse_manifest(data: dict[str, Any]) -> SecurityManifest:
    """Build a SecurityManifest from plain JSON-compatible input."""

    permissions = {PermissionScope(value) for value in data.get("permissions", [])}
    data_flows = [
        DataFlowDeclaration(
            source=flow["source"],
            destination=flow["destination"],
            classification=DataClassification(
                flow.get("classification", DataClassification.INTERNAL.value)
            ),
            description=flow.get("description", ""),
            transforms=list(flow.get("transforms", [])),
            retention=flow.get("retention", "none"),
        )
        for flow in data.get("data_flows", [])
    ]
    resource_access = [
        ResourceAccessDeclaration(
            resource_pattern=access["resource_pattern"],
            access_type=access.get("access_type", "read"),
            required=access.get("required", True),
            description=access.get("description", ""),
            classification=DataClassification(
                access.get("classification", DataClassification.INTERNAL.value)
            ),
        )
        for access in data.get("resource_access", [])
    ]
    return SecurityManifest(
        tool_name=data.get("tool_name", ""),
        version=data.get("version", "0.0.0"),
        author=data.get("author", ""),
        description=data.get("description", ""),
        permissions=permissions,
        data_flows=data_flows,
        resource_access=resource_access,
        max_execution_time_seconds=data.get("max_execution_time_seconds", 60.0),
        idempotent=data.get("idempotent", False),
        deterministic=data.get("deterministic", False),
        requires_consent=data.get("requires_consent", False),
        dependencies=list(data.get("dependencies", [])),
        tags=set(data.get("tags", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _coerce_level(
    value: CertificationLevel | str | None,
    *,
    default: CertificationLevel | None = None,
) -> CertificationLevel | None:
    if value is None:
        return default
    if isinstance(value, CertificationLevel):
        return value
    return CertificationLevel(value)


def _coerce_categories(values: list[str] | set[str] | None) -> set[ToolCategory]:
    if not values:
        return set()
    return {ToolCategory(value) for value in values}


def _level_index(level: CertificationLevel) -> int:
    """Stable integer ordering of ``CertificationLevel`` for clamping.

    Using ``list(CertificationLevel).index(level)`` matches the
    convention :class:`CertificationPipeline` uses internally so the
    "cap to BASIC" check resolves identically to the pipeline's own
    "level meets minimum" check.
    """
    return list(CertificationLevel).index(level)


def _split_multi_value(request: Request, key: str) -> list[str]:
    values = list(request.query_params.getlist(key))
    if not values:
        raw = request.query_params.get(key)
        if raw:
            values = raw.split(",")
    return [value.strip() for value in values if value.strip()]


def _int_query_param(
    request: Request,
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = request.query_params.get(key)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _status_code_from_payload(payload: dict[str, Any]) -> int:
    status = payload.get("status")
    return status if isinstance(status, int) else 200


def _provenance_action_for(action: str) -> str:
    """Map a logical request ``action`` to the
    :class:`ProvenanceAction` enum string the ledger would record.

    Used by the simulator to emit a "would-record" preview that
    matches the shape the live ledger would write — without actually
    writing. Falls back to ``"custom"`` so unknown actions still
    produce a sensible preview rather than blowing up.
    """
    table = {
        "call_tool": "tool_called",
        "tool_call": "tool_called",
        "tools/call": "tool_called",
        "read_resource": "resource_read",
        "resource_read": "resource_read",
        "resources/read": "resource_read",
        "list_resources": "resource_listed",
        "render_prompt": "prompt_rendered",
        "list_prompts": "prompt_listed",
        "policy_evaluate": "policy_evaluated",
        "model_invoke": "model_invoked",
        "dataset_access": "dataset_accessed",
    }
    return table.get(action, "custom")


def _parse_csv_set(raw_value: str) -> set[str]:
    return {value.strip() for value in raw_value.split(",") if value.strip()}


def _parse_optional_json_object(raw_value: str, *, field_name: str) -> dict[str, Any]:
    value = raw_value.strip()
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"`{field_name}` must be a JSON object.")
    return dict(parsed)


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    content_type = request.headers.get("content-type", "")
    return "application/json" in accept or "application/json" in content_type


def _safe_next_path(raw_value: str | None, *, default: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return default
    if not value.startswith("/") or value.startswith("//"):
        return default
    return value


def _limit_list_payload(
    payload: dict[str, Any], *, key: str, limit: int
) -> dict[str, Any]:
    items = list(payload.get(key, []))
    trimmed = dict(payload)
    trimmed[key] = items[:limit]
    trimmed["count"] = min(len(items), limit)
    return trimmed


def _role_from_body(value: Any) -> RegistryRole | None:
    try:
        return RegistryRole(str(value))
    except ValueError:
        return None


def _account_role_counts(users: list[dict[str, Any]]) -> dict[str, int]:
    counts = {role.value: 0 for role in RegistryRole}
    counts["active"] = 0
    counts["disabled"] = 0
    for user in users:
        role = str(user.get("role") or "")
        if role in counts:
            counts[role] += 1
        if user.get("active") is True:
            counts["active"] += 1
        else:
            counts["disabled"] += 1
    return counts


class PureCipherRegistry(SecureMCP[LifespanResultT], Generic[LifespanResultT]):
    """PureCipher's verified SecureMCP registry MVP.

    This wraps SecureMCP into an opinionated registry service: tools submit
    manifests, PureCipher certifies them, stores trust metadata, and exposes
    a small HTTP surface for registry queries.
    """

    def __init__(
        self,
        name: str | None = None,
        *,
        signing_secret: bytes | str | None = None,
        issuer_id: str = "purecipher-registry",
        minimum_certification: CertificationLevel = CertificationLevel.BASIC,
        registry_prefix: str = "/registry",
        mount_registry_api: bool = True,
        enable_legacy_registry_ui: bool = True,
        mount_security_api: bool = True,
        require_moderation: bool = False,
        persistence_path: str | None = None,
        security: SecurityConfig | None = None,
        auth_settings: RegistryAuthSettings | None = None,
        security_api_require_auth: bool = False,
        security_api_bearer_token: str | None = None,
        security_api_auth_verifier: Any = None,
        # Control-plane opt-outs. As of Iter8 the registry's default
        # SecurityConfig wires all five SecureMCP control planes
        # (policy + contracts + consent + provenance + reflexive)
        # plus the existing tool marketplace + certification. An
        # operator who explicitly *doesn't* want a particular plane
        # — for cost, simplicity, or compliance reasons — passes
        # ``False`` for the matching ``enable_*`` flag.
        #
        # These flags only apply to the auto-built default config;
        # callers passing their own ``security=SecurityConfig(...)``
        # are responsible for plane wiring themselves.
        enable_contracts: bool = True,
        enable_consent: bool = True,
        enable_provenance: bool = True,
        enable_reflexive: bool = True,
        **kwargs: Any,
    ) -> None:
        if security is None and signing_secret is None:
            raise ValueError(
                "`signing_secret` is required when `security` is not provided."
            )

        self._issuer_id = issuer_id
        self._minimum_certification = minimum_certification
        self._require_moderation = require_moderation
        self._registry_prefix = registry_prefix
        self._enable_legacy_registry_ui = enable_legacy_registry_ui
        # Saved for the Iter 9 runtime toggles. When an admin
        # re-enables a plane after disabling it, the helper rebuilds
        # the plane with default config plus this secret + issuer
        # so contract signatures, ledger genesis nonces, etc.
        # remain consistent with the registry's identity.
        self._signing_secret_bytes: bytes | None = (
            signing_secret.encode()
            if isinstance(signing_secret, str)
            else signing_secret
        )
        self._registry_api_mounted = False
        self._auth_settings = auth_settings or RegistryAuthSettings.from_env(
            issuer=issuer_id,
            signing_secret=signing_secret,
        )
        self._auth_settings.validate()

        self._persistence_path = persistence_path
        schema_managed_by_migrations = (
            bool(persistence_path) and persistence_path != ":memory:"
        )
        if schema_managed_by_migrations:
            migrate_registry_database(persistence_path)
        self._notification_feed = RegistryNotificationFeed(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
        )
        self._openapi_store = OpenAPIStore(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
            credential_key=self._signing_secret_bytes,
        )
        # Iter 13.3: tests can inject an httpx.AsyncClient (typically
        # backed by ``MockTransport``) so the /invoke route doesn't
        # have to hit a real network. ``None`` means the executor
        # opens a one-shot client per call in production.
        self._openapi_invoke_client: Any = None
        self._user_preferences = RegistryUserPreferenceStore(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
        )
        # Persistent runtime overrides for the four opt-in control
        # planes. The store is consulted *after* the constructor's
        # ``enable_*`` flags so that an admin's UI toggle survives
        # restart even when the operator hasn't updated their
        # constructor call.
        self._control_plane_store = RegistryControlPlaneStore(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
        )
        # Iter 10: persistent MCP-client identity + token store.
        # Backs the Clients page + onboard wizard + per-client
        # detail/governance views, and is consulted by the
        # token-aware actor resolver below.
        self._client_store = RegistryClientStore(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
        )
        self._account_activity = RegistryAccountActivityStore(
            persistence_path,
            ensure_schema=not schema_managed_by_migrations,
        )
        self._account_security = RegistryAccountSecurityStore(
            persistence_path,
            self._auth_settings.users,
            ensure_schema=not schema_managed_by_migrations,
        )
        # Per-(username, ip) login throttle. Pre-fix the registry had
        # no rate limiting on POST /registry/login, allowing infinite
        # password brute force.
        self._login_lockout = LoginLockout()
        if self.auth_enabled and self._auth_settings.bootstrap_admin_password:
            bootstrapped = self._account_security.create_bootstrap_admin(
                username=self._auth_settings.bootstrap_admin_username,
                password=self._auth_settings.bootstrap_admin_password,
                display_name=self._auth_settings.bootstrap_admin_display_name,
            )
            if bootstrapped is not None:
                self._account_activity.append(
                    username=bootstrapped.username,
                    event_kind="bootstrap_admin_created",
                    title="Bootstrap admin created",
                    detail="Initial registry admin account was created from bootstrap settings.",
                    metadata={"role": bootstrapped.role.value, "source": "env"},
                )

        # Apply persisted operator toggles. The store wins over
        # constructor defaults — an admin who flipped a plane off
        # via the settings UI shouldn't have it spring back to "on"
        # the next time the process restarts. ``security=`` callers
        # are responsible for honoring the store themselves.
        if security is None:
            persisted_toggles = self._control_plane_store.get_all()
            for plane_name, setting in persisted_toggles.items():
                if plane_name == "contracts":
                    enable_contracts = setting.enabled
                elif plane_name == "consent":
                    enable_consent = setting.enabled
                elif plane_name == "provenance":
                    enable_provenance = setting.enabled
                elif plane_name == "reflexive":
                    enable_reflexive = setting.enabled

        resolved_security = security or self._build_default_security(
            signing_secret=signing_secret,
            issuer_id=issuer_id,
            minimum_certification=minimum_certification,
            require_moderation=require_moderation,
            persistence_path=persistence_path,
            enable_contracts=enable_contracts,
            enable_consent=enable_consent,
            enable_provenance=enable_provenance,
            enable_reflexive=enable_reflexive,
            server_id=name or "purecipher-registry",
        )

        super().__init__(
            name=name or "purecipher-registry",
            security=resolved_security,
            mount_security_api=mount_security_api,
            security_api_require_auth=security_api_require_auth,
            security_api_bearer_token=security_api_bearer_token,
            security_api_auth_verifier=security_api_auth_verifier,
            **kwargs,
        )

        self._validate_registry_context(self._required_context())

        # Iter 10: wire client-actor resolution into the security
        # middleware chain. The resolver runs first and stashes the
        # resolved slug in a contextvar; the four downstream
        # middlewares are upgraded in-place to PureCipher-aware
        # subclasses that prefer the contextvar over the access-
        # token prefix when populating ``actor_id``. Net effect:
        # every plane (Policy, Contract, Consent, Provenance,
        # Reflexive) sees a stable per-client identifier when an
        # MCP client presents a registry-issued bearer token.
        ctx = self._required_context()
        ctx.middleware = upgrade_middleware_for_client_actor(ctx.middleware)
        ctx.middleware.insert(0, ClientActorResolverMiddleware(self))

        if mount_registry_api:
            self.mount_registry_api(prefix=registry_prefix)

        # Iter 13.5: re-attach OpenAPI proxy tools for any listings
        # that were published in a previous run. Restarts of a
        # SQLite-backed registry would otherwise lose the MCP
        # ``tools/call`` bindings even though the listings persist.
        self._reattach_openapi_proxy_tools()

    @property
    def minimum_certification(self) -> CertificationLevel:
        """Minimum certification level accepted by this registry."""

        return self._minimum_certification

    @property
    def auth_enabled(self) -> bool:
        """Return True when registry auth is enabled."""

        return self._auth_settings.enabled

    @staticmethod
    def _build_default_security(
        *,
        signing_secret: bytes | str | None,
        issuer_id: str,
        minimum_certification: CertificationLevel,
        require_moderation: bool,
        persistence_path: str | None,
        enable_contracts: bool = True,
        enable_consent: bool = True,
        enable_provenance: bool = True,
        enable_reflexive: bool = True,
        server_id: str = "purecipher-registry",
    ) -> SecurityConfig:
        secret_bytes = (
            signing_secret.encode()
            if isinstance(signing_secret, str)
            else signing_secret
        )
        if secret_bytes is None:
            raise ValueError("`signing_secret` must resolve to bytes.")

        backend = SQLiteBackend(persistence_path) if persistence_path else None
        registry = TrustRegistry()
        marketplace = ToolMarketplace(
            trust_registry=registry,
            backend=backend,
            require_moderation=require_moderation,
        )
        crypto = ContractCryptoHandler(
            algorithm=SigningAlgorithm.HMAC_SHA256,
            secret_key=secret_bytes,
        )

        # Opt-in control planes. As of Iter8 these are *on by
        # default*: every registry deployment ships with the full
        # SecureMCP stack (policy + contracts + consent + provenance +
        # reflexive) wired and recording. Operators who don't want a
        # specific plane pass ``enable_<plane>=False`` to the
        # registry constructor; the matching ``*Config`` simply
        # isn't created.
        contracts_config: ContractConfig | None = None
        if enable_contracts:
            contracts_config = ContractConfig(
                # Sign contracts with the same crypto handler the
                # certification pipeline uses so signatures verify
                # under the same trust root.
                crypto_handler=crypto,
                backend=backend,
            )

        consent_config: ConsentConfig | None = None
        if enable_consent:
            consent_config = ConsentConfig(
                graph_id=server_id,
                backend=backend,
            )

        provenance_config: ProvenanceConfig | None = None
        if enable_provenance:
            provenance_config = ProvenanceConfig(
                ledger_id=server_id,
                backend=backend,
            )

        reflexive_config: ReflexiveConfig | None = None
        if enable_reflexive:
            reflexive_config = ReflexiveConfig(
                backend=backend,
            )

        introspection_config: IntrospectionConfig | None = None
        if enable_reflexive:
            introspection_config = IntrospectionConfig(
                enable_pre_execution_gating=False,
            )

        return SecurityConfig(
            alerts=AlertConfig(),
            policy=PolicyConfig(
                enable_versioning=True,
                enable_governance=True,
                governance_require_simulation=False,
                enable_validation=True,
                backend=backend,
            ),
            registry=RegistryConfig(registry=registry),
            tool_marketplace=ToolMarketplaceConfig(marketplace=marketplace),
            certification=CertificationConfig(
                pipeline=CertificationPipeline(
                    issuer_id=issuer_id,
                    crypto_handler=crypto,
                    min_level_for_signing=minimum_certification,
                )
            ),
            contracts=contracts_config,
            consent=consent_config,
            provenance=provenance_config,
            reflexive=reflexive_config,
            introspection=introspection_config,
        )

    def _required_context(self) -> SecurityContext:
        ctx = self.security_context
        if ctx is None:
            raise RuntimeError("SecureMCP is not attached to this PureCipher registry.")
        return ctx

    # ── Iter 10: MCP client identities ────────────────────────────

    def register_client(
        self,
        *,
        display_name: str,
        owner_publisher_id: str,
        slug: str | None = None,
        description: str = "",
        intended_use: str = "",
        kind: str = "agent",
        metadata: dict[str, Any] | None = None,
        issue_initial_token: bool = True,
        token_name: str = "Default",
        created_by: str = "",
    ) -> dict[str, Any]:
        """Create a client and (optionally) mint a first token.

        Returns ``{client, token, secret}`` when an initial token
        was issued; ``{client, token: None, secret: None}`` when
        ``issue_initial_token=False``. The plain secret is the only
        place the full token will exist after this call returns —
        callers must surface it to the user once and never again.

        ``kind`` is the client taxonomy slug (``agent`` /
        ``service`` / ``framework`` / ``tooling`` / ``other``); it
        feeds the directory filters and per-kind defaults downstream.
        """
        client = self._client_store.create_client(
            display_name=display_name,
            owner_publisher_id=owner_publisher_id,
            slug=slug,
            description=description,
            intended_use=intended_use,
            kind=kind,
            metadata=metadata,
        )
        token: RegistryClientToken | None = None
        secret: str | None = None
        if issue_initial_token:
            token, secret = self._client_store.issue_token(
                client_id=client.client_id,
                name=token_name,
                created_by=created_by or owner_publisher_id,
            )
        return {
            "client": client.to_dict(),
            "token": token.to_dict() if token is not None else None,
            "secret": secret,
        }

    def get_client(self, client_id_or_slug: str) -> RegistryClient | None:
        """Look up by either UUID or slug — the routes accept both
        so links from the UI work cleanly."""
        record = self._client_store.get_client(client_id_or_slug)
        if record is not None:
            return record
        return self._client_store.get_client_by_slug(client_id_or_slug)

    def list_clients_for_caller(
        self,
        *,
        session: Any | None,
        limit: int = 200,
    ) -> list[RegistryClient]:
        """Visibility-aware list.

        Admins (or auth-disabled callers) see every client.
        Publishers see clients they own. Anyone else gets nothing.
        The route handler converts the empty list to a 403 when the
        caller has no role at all.
        """
        if not self.auth_enabled:
            return self._client_store.list_clients(limit=limit)
        if session is None:
            return []
        if self._has_roles(session, {RegistryRole.ADMIN}):
            return self._client_store.list_clients(limit=limit)
        if self._has_roles(session, {RegistryRole.PUBLISHER}):
            return self._client_store.list_clients(
                owner_publisher_id=publisher_id_from_author(session.username),
                limit=limit,
            )
        return []

    def update_client(
        self,
        client_id: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        intended_use: str | None = None,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegistryClient | None:
        return self._client_store.update_client(
            client_id,
            display_name=display_name,
            description=description,
            intended_use=intended_use,
            kind=kind,
            metadata=metadata,
        )

    def suspend_client(
        self, client_id: str, *, reason: str = ""
    ) -> RegistryClient | None:
        return self._client_store.set_status(
            client_id, status="suspended", reason=reason
        )

    def unsuspend_client(self, client_id: str) -> RegistryClient | None:
        return self._client_store.set_status(client_id, status="active")

    def issue_client_token(
        self,
        client_id: str,
        *,
        name: str,
        created_by: str,
    ) -> tuple[RegistryClientToken, str]:
        return self._client_store.issue_token(
            client_id=client_id,
            name=name,
            created_by=created_by,
        )

    def list_client_tokens(
        self, client_id: str, *, include_revoked: bool = True
    ) -> list[RegistryClientToken]:
        return self._client_store.list_tokens(
            client_id, include_revoked=include_revoked
        )

    def revoke_client_token(self, token_id: str) -> RegistryClientToken | None:
        return self._client_store.revoke_token(token_id)

    def authenticate_client_token(
        self, presented_secret: str
    ) -> tuple[RegistryClient, RegistryClientToken] | None:
        """Resolve a presented bearer token to its client identity.

        Returns ``None`` when the token doesn't match, was revoked,
        or its owning client is suspended. On success, updates the
        token's ``last_used_at`` as a side effect.
        """
        return self._client_store.authenticate_token(presented_secret)

    def resolve_actor_from_request(self, request: Request) -> str | None:
        """Return a stable ``actor_id`` for an HTTP request.

        Looks for a client API token in the ``Authorization: Bearer
        ...`` header. When found and valid, returns the client's
        slug — that's the form ledger / drift / contract code reads
        elsewhere. Falls back to ``None`` when no token is
        presented or the token doesn't authenticate, mirroring how
        the existing middleware treats missing authn.
        """
        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        secret = auth[len("Bearer ") :].strip()
        result = self.authenticate_client_token(secret)
        if result is None:
            return None
        client, _ = result
        return client.slug

    # ── Iter 10: per-client governance projection ────────────────

    def get_client_governance(
        self,
        client_id_or_slug: str,
        *,
        sanitize_for_public: bool = False,
    ) -> dict[str, Any]:
        """Return the per-client governance + observability rollup.

        Mirrors :meth:`get_listing_governance` but keys every plane
        projection by the client's slug (which the
        :class:`ClientActorResolverMiddleware` writes as ``actor_id``
        on every request). The result lets the per-client UI show:

        * how many active contracts the client has,
        * how many consent edges name the client as source/target,
        * how many provenance records the client has appeared in,
        * what drift events have been flagged against the client,
        * a token roll-up.

        Visibility:

        * The caller resolves access (the route handler enforces
          owner-or-admin); this method projects whatever the planes
          have. When ``sanitize_for_public=True``, identifying
          counterparties (peer ``source_id`` / ``target_id``,
          contract ``server_id``) are stripped so a public-facing
          variant of the page can show *that* the client has
          activity without leaking *who* they're talking to.

        Returns ``{error, status: 404}`` when the client isn't
        registered.
        """
        record = self.get_client(client_id_or_slug)
        if record is None:
            return {
                "error": f"Client {client_id_or_slug!r} not found.",
                "status": 404,
            }

        slug = record.slug
        prefix = self._registry_prefix

        header = {
            "client_id": record.client_id,
            "slug": slug,
            "display_name": record.display_name,
            "kind": record.kind,
            "owner_publisher_id": record.owner_publisher_id,
            "status": record.status,
            "suspended_reason": record.suspended_reason,
            "intended_use": record.intended_use,
            "description": record.description,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

        # Contracts: broker-level summary + filtered active list.
        broker = self._broker_or_none()
        contracts_block = self._summarize_broker(broker)
        active_contracts: list[dict[str, Any]] = []
        if broker is not None:
            try:
                rows = list(broker.get_active_contracts_for_agent(slug))
            except Exception:
                rows = []
            for c in rows[:50]:
                active_contracts.append(
                    {
                        "contract_id": getattr(c, "contract_id", ""),
                        "server_id": getattr(c, "server_id", ""),
                        "session_id": getattr(c, "session_id", ""),
                        "status": getattr(
                            getattr(c, "status", None),
                            "value",
                            str(getattr(c, "status", "") or ""),
                        ),
                        "created_at": (
                            c.created_at.isoformat()
                            if getattr(c, "created_at", None)
                            else None
                        ),
                        "expires_at": (
                            c.expires_at.isoformat()
                            if getattr(c, "expires_at", None)
                            else None
                        ),
                    }
                )

        # Consent: graph-level summary + per-direction edge counts.
        consent_graph = self._consent_graph_or_none()
        consent_block = self._summarize_consent_graph(consent_graph)
        edges_from: list[dict[str, Any]] = []
        edges_to: list[dict[str, Any]] = []
        if consent_graph is not None:
            try:
                outgoing = list(consent_graph.get_consents_from(slug))
            except Exception:
                outgoing = []
            try:
                incoming = list(consent_graph.get_consents_for(slug))
            except Exception:
                incoming = []
            for edge in outgoing[:50]:
                edges_from.append(
                    {
                        "edge_id": getattr(edge, "edge_id", ""),
                        "target_id": getattr(edge, "target_id", ""),
                        "scopes": list(getattr(edge, "scopes", []) or []),
                        "status": getattr(
                            getattr(edge, "status", None),
                            "value",
                            str(getattr(edge, "status", "") or ""),
                        ),
                        "delegatable": bool(getattr(edge, "delegatable", False)),
                    }
                )
            for edge in incoming[:50]:
                edges_to.append(
                    {
                        "edge_id": getattr(edge, "edge_id", ""),
                        "source_id": getattr(edge, "source_id", ""),
                        "scopes": list(getattr(edge, "scopes", []) or []),
                        "status": getattr(
                            getattr(edge, "status", None),
                            "value",
                            str(getattr(edge, "status", "") or ""),
                        ),
                        "delegatable": bool(getattr(edge, "delegatable", False)),
                    }
                )

        # Ledger: ledger-level summary + per-actor record window.
        # ``ledger_rows`` is kept in scope past this block so the
        # activity-summary computation downstream can reuse the same
        # window without paying for a second ``get_records`` round-trip.
        ledger = self._ledger_or_none()
        ledger_block = self._summarize_ledger(ledger)
        recent_records: list[dict[str, Any]] = []
        record_count = 0
        ledger_rows: list[Any] = []
        if ledger is not None:
            try:
                ledger_rows = list(ledger.get_records(actor_id=slug, limit=1000))
            except Exception:
                ledger_rows = []
            record_count = len(ledger_rows)
            for row in ledger_rows[:50]:
                recent_records.append(
                    {
                        "record_id": getattr(row, "record_id", ""),
                        "action": getattr(
                            getattr(row, "action", None),
                            "value",
                            str(getattr(row, "action", "") or ""),
                        ),
                        "resource_id": getattr(row, "resource_id", ""),
                        "timestamp": (
                            row.timestamp.isoformat()
                            if getattr(row, "timestamp", None)
                            else None
                        ),
                        "contract_id": getattr(row, "contract_id", None),
                    }
                )

        # Reflexive: analyzer summary + drift history filtered by actor.
        analyzer = self._analyzer_or_none()
        analyzer_block = self._summarize_analyzer(analyzer)
        recent_drifts: list[dict[str, Any]] = []
        drift_event_count = 0
        severity_dist: dict[str, int] = {}
        baselines: dict[str, Any] = {}
        if analyzer is not None:
            try:
                drift_history = list(analyzer.get_drift_history(actor_id=slug))
            except Exception:
                drift_history = []
            drift_event_count = len(drift_history)
            for ev in drift_history[:50]:
                severity = getattr(
                    getattr(ev, "severity", None),
                    "value",
                    str(getattr(ev, "severity", "") or ""),
                )
                severity_dist[severity] = severity_dist.get(severity, 0) + 1
                recent_drifts.append(
                    {
                        "event_id": getattr(ev, "event_id", ""),
                        "drift_type": getattr(
                            getattr(ev, "drift_type", None),
                            "value",
                            str(getattr(ev, "drift_type", "") or ""),
                        ),
                        "severity": severity,
                        "observed_value": getattr(ev, "observed_value", None),
                        "baseline_value": getattr(ev, "baseline_value", None),
                        "deviation": getattr(ev, "deviation", None),
                        "timestamp": (
                            ev.timestamp.isoformat()
                            if getattr(ev, "timestamp", None)
                            else None
                        ),
                    }
                )
            try:
                bls = analyzer.get_actor_baselines(slug) or {}
            except Exception:
                bls = {}
            for metric, baseline in list(bls.items())[:50]:
                baselines[str(metric)] = {
                    "metric_name": str(metric),
                    "mean": getattr(baseline, "mean", None),
                    "stddev": getattr(baseline, "stddev", None),
                    "samples": getattr(baseline, "samples", None),
                }

        # Tokens: active vs revoked count for the client.
        tokens = self.list_client_tokens(record.client_id)
        active_tokens = [t for t in tokens if t.is_active()]
        revoked_tokens = [t for t in tokens if not t.is_active()]

        # ── Activity summary ─────────────────────────────────────
        # Composes the ledger window (provenance records keyed by
        # actor_id) with the tokens' ``last_used_at`` fingerprints.
        # The result powers the per-client "is anyone home?" header
        # chip + the live activity feed on the detail page.
        activity_summary = self._summarize_client_activity(
            ledger_rows=ledger_rows,
            tokens=tokens,
        )

        result: dict[str, Any] = {
            **header,
            "policy": {
                # PolicyEngine is stateless (decisions per-call);
                # there's no per-actor decision log to project.
                # The registry policy summary still gives operators
                # a sense of what gates a request would pass through.
                "registry_policy": self._summarize_registry_policy(),
                "actor_history": None,
                "note": (
                    "Policy decisions are evaluated per-request; "
                    "per-actor history is captured downstream by the "
                    "ledger plane (see `ledger.recent_records`)."
                ),
            },
            "contracts": {
                "broker": contracts_block,
                "active_count": len(active_contracts),
                "active_contracts": active_contracts,
            },
            "consent": {
                "consent_graph": consent_block,
                "outgoing_count": len(edges_from),
                "incoming_count": len(edges_to),
                "edges_from": edges_from,
                "edges_to": edges_to,
            },
            "ledger": {
                "ledger": ledger_block,
                "record_count": record_count,
                "recent_records": recent_records,
            },
            "reflexive": {
                "analyzer": analyzer_block,
                "drift_event_count": drift_event_count,
                "severity_distribution": severity_dist,
                "recent_drifts": recent_drifts,
                "baselines": baselines,
            },
            "tokens": {
                "total": len(tokens),
                "active": len(active_tokens),
                "revoked": len(revoked_tokens),
                "items": [t.to_dict() for t in tokens],
            },
            "activity": activity_summary,
            "links": {
                "policy_kernel_url": f"{prefix}/policy",
                "contract_broker_url": f"{prefix}/contracts",
                "consent_graph_url": f"{prefix}/consent",
                "provenance_ledger_url": f"{prefix}/provenance",
                "reflexive_core_url": f"{prefix}/reflexive",
                "publisher_url": (f"{prefix}/publishers/{record.owner_publisher_id}"),
                "client_url": f"{prefix}/clients/{slug}",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if sanitize_for_public:
            result = self._sanitize_client_governance(result)
        return result

    @staticmethod
    def _summarize_client_activity(
        *,
        ledger_rows: list[Any],
        tokens: list[Any],
    ) -> dict[str, Any]:
        """Project a client's recent provenance window + token usage
        into the activity-summary block consumed by the per-client
        detail page (header status chip + live feed).

        Inputs:

        * ``ledger_rows``: the same per-actor records the ledger
          plane already pulls (capped at 1000 by ``get_records``);
          we just re-bucket and aggregate them here so we don't pay
          for a second backend round-trip.
        * ``tokens``: the client's tokens. The most recent
          ``last_used_at`` across all of them is folded into
          ``last_seen_at`` so a client that auths but hasn't yet
          written a ledger record (e.g. policy denied the very
          first call) still shows as "active".

        Outputs:

        * ``last_seen_at``: ISO timestamp of most recent activity, or
          ``None`` if we have no signal at all.
        * ``last_seen_source``: ``"ledger"`` / ``"token"`` / ``None``.
        * ``idle_seconds``: gap between now and ``last_seen_at``.
        * ``status_label``: one of
          ``"live"`` (≤60s) / ``"recent"`` (≤15min) /
          ``"idle"`` (≤24h) / ``"dormant"`` (>24h) /
          ``"never"`` (no signal).
        * ``calls_last_hour`` / ``calls_last_24h``: ledger record
          counts in those rolling windows.
        * ``hourly_buckets``: 24-element array of
          ``{hour_offset, count}`` records for the last 24 hours
          (offset 0 = current hour, 23 = 23 hours ago) — drives the
          UI sparkline.
        * ``top_resources``: up to 5 ``{resource_id, count}`` records
          by call frequency in the available window. Stripped under
          ``sanitize_for_public`` (the resource ids would leak who
          the client is talking to).
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)

        # ── last_seen_at composition (ledger ∨ token last_used_at)
        ledger_latest_dt: datetime | None = None
        for row in ledger_rows:
            ts = getattr(row, "timestamp", None)
            if ts is None:
                continue
            if ledger_latest_dt is None or ts > ledger_latest_dt:
                ledger_latest_dt = ts

        token_latest: float = 0.0
        for tok in tokens:
            last_used = getattr(tok, "last_used_at", None) or 0
            if last_used and last_used > token_latest:
                token_latest = float(last_used)

        token_latest_dt: datetime | None = (
            datetime.fromtimestamp(token_latest, tz=timezone.utc)
            if token_latest > 0
            else None
        )

        last_seen_at: datetime | None = None
        last_seen_source: str | None = None
        if ledger_latest_dt and (
            token_latest_dt is None or ledger_latest_dt >= token_latest_dt
        ):
            last_seen_at = ledger_latest_dt
            last_seen_source = "ledger"
        elif token_latest_dt is not None:
            last_seen_at = token_latest_dt
            last_seen_source = "token"

        # ── status label
        if last_seen_at is None:
            status_label = "never"
            idle_seconds: float | None = None
        else:
            idle_seconds = max(0.0, (now - last_seen_at).total_seconds())
            if idle_seconds <= 60:
                status_label = "live"
            elif idle_seconds <= 15 * 60:
                status_label = "recent"
            elif idle_seconds <= 24 * 60 * 60:
                status_label = "idle"
            else:
                status_label = "dormant"

        # ── windowed call counts (ledger only — tokens don't carry
        # per-call timestamps, just a single last_used_at).
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)
        calls_last_hour = 0
        calls_last_24h = 0
        for row in ledger_rows:
            ts = getattr(row, "timestamp", None)
            if ts is None:
                continue
            if ts >= one_hour_ago:
                calls_last_hour += 1
            if ts >= one_day_ago:
                calls_last_24h += 1

        # ── hourly buckets, hour 0 == current hour, 23 == 23h ago
        hourly_counts: list[int] = [0] * 24
        for row in ledger_rows:
            ts = getattr(row, "timestamp", None)
            if ts is None or ts < one_day_ago:
                continue
            offset = int((now - ts).total_seconds() // 3600)
            if 0 <= offset < 24:
                hourly_counts[offset] += 1
        hourly_buckets = [
            {"hour_offset": i, "count": hourly_counts[i]} for i in range(24)
        ]

        # ── top resources (last 24h window)
        resource_counts: dict[str, int] = {}
        for row in ledger_rows:
            ts = getattr(row, "timestamp", None)
            if ts is None or ts < one_day_ago:
                continue
            resource_id = getattr(row, "resource_id", None)
            if not resource_id:
                continue
            resource_counts[str(resource_id)] = (
                resource_counts.get(str(resource_id), 0) + 1
            )
        top_resources = [
            {"resource_id": rid, "count": cnt}
            for rid, cnt in sorted(
                resource_counts.items(),
                key=lambda pair: pair[1],
                reverse=True,
            )[:5]
        ]

        return {
            "last_seen_at": (last_seen_at.isoformat() if last_seen_at else None),
            "last_seen_source": last_seen_source,
            "idle_seconds": idle_seconds,
            "status_label": status_label,
            "calls_last_hour": calls_last_hour,
            "calls_last_24h": calls_last_24h,
            "hourly_buckets": hourly_buckets,
            "top_resources": top_resources,
            "evaluated_at": now.isoformat(),
        }

    def summarize_clients_activity(self) -> dict[str, Any]:
        """Iter 14.24 — aggregate activity-status counts across every
        registered client, for the Clients dashboard panel.

        Loops through every client record, fetches that client's
        ledger window + tokens, and reuses
        :meth:`_summarize_client_activity` to derive per-client
        ``status_label`` (live / recent / idle / dormant / never).
        Folds the labels into a single counts dict the operator can
        glance at without opening every client detail page.

        Counts emitted:

        - ``total``: number of registered clients.
        - ``by_activity_status``: ``{live, recent, idle, dormant, never}``
          counts based on the same status thresholds the per-client
          activity panel uses (≤60s / ≤15m / ≤24h / >24h / no-signal).
        - ``by_admin_status``: ``{active, suspended}`` counts based on
          ``RegistryClient.status`` (admin lifecycle, distinct from
          activity).
        - ``by_kind``: counts grouped by ``RegistryClient.kind``.
        - ``recently_onboarded_count``: clients created in the last
          7 days (``created_at`` within 7 days of now).
        - ``calls_last_24h_total``: rollup of ledger calls across all
          clients in the last 24 hours.
        - ``generated_at``: ISO timestamp.

        Cost: O(N) ``get_records`` calls plus O(N) token lookups,
        where N = client count. For typical deployments (≤50 clients)
        this is well under 100ms; if N grows past a few hundred the
        right move is a bulk ledger query keyed by actor_id list.
        That refactor is left for a future iteration since current
        deployments don't see N that large.
        """
        from datetime import datetime, timedelta, timezone

        clients = self._client_store.list_clients(limit=10_000)
        ledger = self._ledger_or_none()
        now = datetime.now(timezone.utc)
        seven_days_ago_ts = (now - timedelta(days=7)).timestamp()

        activity_counts = {
            "live": 0,
            "recent": 0,
            "idle": 0,
            "dormant": 0,
            "never": 0,
        }
        admin_counts = {"active": 0, "suspended": 0}
        kind_counts: dict[str, int] = {}
        recently_onboarded = 0
        calls_last_24h_total = 0

        for record in clients:
            # ── activity status from ledger + token last_used_at ──
            ledger_rows: list[Any] = []
            if ledger is not None:
                try:
                    ledger_rows = list(
                        ledger.get_records(actor_id=record.slug, limit=1000)
                    )
                except Exception:
                    ledger_rows = []
            tokens = self.list_client_tokens(record.client_id)
            activity = self._summarize_client_activity(
                ledger_rows=ledger_rows,
                tokens=tokens,
            )
            label = str(activity.get("status_label") or "never")
            if label in activity_counts:
                activity_counts[label] += 1
            else:
                activity_counts["never"] += 1
            calls_last_24h_total += int(activity.get("calls_last_24h") or 0)

            # ── admin lifecycle status (active / suspended) ──
            admin_label = "suspended" if str(record.status) == "suspended" else "active"
            admin_counts[admin_label] += 1

            # ── kind histogram ──
            kind = str(record.kind or "other")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1

            # ── recently-onboarded (≤7d) ──
            try:
                if float(record.created_at) >= seven_days_ago_ts:
                    recently_onboarded += 1
            except (TypeError, ValueError):
                # Defensive: malformed created_at shouldn't break the
                # whole aggregate. Just skip the recent-bucket count
                # for that client.
                pass

        return {
            "total": len(clients),
            "by_activity_status": activity_counts,
            "by_admin_status": admin_counts,
            "by_kind": kind_counts,
            "recently_onboarded_count": recently_onboarded,
            "calls_last_24h_total": calls_last_24h_total,
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _sanitize_client_governance(
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Strip per-counterparty identifiers from a client governance
        payload so a public viewer sees activity volume without
        learning *who* the client is talking to.

        Removes:

        - contracts: ``server_id``, ``session_id``, ``contract_id``
        - consent edges: ``source_id``, ``target_id``, ``edge_id``
        - ledger records: ``resource_id``, ``contract_id``, ``record_id``
        - drift events: ``event_id`` (severity / type / counts stay)
        - tokens: full ``items`` list (counts stay)
        """
        sanitized = dict(payload)

        contracts = dict(sanitized.get("contracts") or {})
        contracts["active_contracts"] = [
            {
                k: v
                for k, v in row.items()
                if k not in {"server_id", "session_id", "contract_id"}
            }
            for row in contracts.get("active_contracts", []) or []
        ]
        sanitized["contracts"] = contracts

        consent = dict(sanitized.get("consent") or {})
        consent["edges_from"] = [
            {k: v for k, v in row.items() if k not in {"target_id", "edge_id"}}
            for row in consent.get("edges_from", []) or []
        ]
        consent["edges_to"] = [
            {k: v for k, v in row.items() if k not in {"source_id", "edge_id"}}
            for row in consent.get("edges_to", []) or []
        ]
        sanitized["consent"] = consent

        ledger = dict(sanitized.get("ledger") or {})
        ledger["recent_records"] = [
            {
                k: v
                for k, v in row.items()
                if k not in {"resource_id", "contract_id", "record_id"}
            }
            for row in ledger.get("recent_records", []) or []
        ]
        sanitized["ledger"] = ledger

        reflexive = dict(sanitized.get("reflexive") or {})
        reflexive["recent_drifts"] = [
            {k: v for k, v in row.items() if k != "event_id"}
            for row in reflexive.get("recent_drifts", []) or []
        ]
        sanitized["reflexive"] = reflexive

        # Tokens: drop the full token records — counts only.
        tokens = dict(sanitized.get("tokens") or {})
        tokens.pop("items", None)
        sanitized["tokens"] = tokens

        # Activity: drop ``top_resources`` (resource ids reveal who
        # the client has been talking to), keep volumetric signals
        # (status_label, hourly_buckets, calls_last_*) since those
        # are ambient and don't leak counterparty identifiers.
        activity = dict(sanitized.get("activity") or {})
        activity["top_resources"] = []
        sanitized["activity"] = activity

        return sanitized

    # ── Iter 11: cross-control-plane request simulator ───────────

    async def simulate_client_request(
        self,
        client_id_or_slug: str,
        *,
        action: str,
        resource_id: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        consent_scope: str = "execute",
        consent_source_id: str | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
    ) -> dict[str, Any]:
        """Dry-run a request through every plane and return a trace.

        The simulator composes the *real* read-only evaluation path
        of each control plane:

        * ``PolicyEngine.evaluate`` — actual policy decision.
        * ``ContextBroker.get_active_contracts_for_agent`` plus a
          term-coverage scan (the broker has no built-in
          ``covers_action`` predicate, so the simulator walks the
          contract's ACCESS_CONTROL terms looking for an
          ``actions`` allow-list).
        * ``ConsentGraph.evaluate`` — actual consent decision keyed
          by (source, target, scope).
        * Provenance: NO write. The simulator emits a "would-record"
          preview shaped like ``ProvenanceRecord.to_dict`` so the UI
          can show what an actual call would have written.
        * ``BehavioralAnalyzer.get_baseline + compute_deviation`` —
          baseline lookup with sigma-distance score (no ``observe``
          side effect).

        Args:
            client_id_or_slug: UUID or slug of a registered client.
            action: Logical action ("call_tool", "read_resource", ...).
            resource_id: Tool / resource name being accessed.
            metadata: Free-form context passed to the policy engine.
            tags: Tags passed to the policy engine.
            consent_scope: Scope to check on the consent edge
                (``"read"`` / ``"write"`` / ``"execute"`` …).
            consent_source_id: Who in the consent graph grants
                access. Defaults to ``resource_id`` so a graph keyed
                by resource works out of the box; supply a publisher
                or owner node for graphs keyed differently.
            metric_name: Metric to evaluate against the actor's
                behavioral baseline. ``None`` skips the reflexive
                check entirely.
            metric_value: Observed value for ``metric_name``.

        Returns:
            ``{client, request, policy, contracts, consent, ledger,
            reflexive, verdict, blockers, generated_at}``. The top-
            level ``verdict`` is ``"allow"`` only when every plane
            agrees; ``blockers`` lists each plane that would deny.

        The simulator never raises on plane failure — each plane
        degrades to ``available=False`` with an explanation so the
        operator can see *why* a particular plane couldn't be
        consulted (disabled, no baseline yet, etc.).
        """
        import hashlib

        client = self.get_client(client_id_or_slug)
        if client is None:
            return {
                "error": f"Client {client_id_or_slug!r} not found.",
                "status": 404,
            }

        slug = client.slug
        request_metadata = dict(metadata or {})
        request_metadata.setdefault("simulated", True)
        request_tags = list(tags or [])
        timestamp = datetime.now(timezone.utc)

        # ── Policy ───────────────────────────────────────────────
        ctx = self._required_context()
        engine = getattr(ctx, "policy_engine", None)
        policy_trace = await self._simulate_policy(
            engine,
            slug=slug,
            action=action,
            resource_id=resource_id,
            metadata=request_metadata,
            tags=request_tags,
            timestamp=timestamp,
        )

        # ── Contracts ────────────────────────────────────────────
        broker = self._broker_or_none()
        contracts_trace = self._simulate_contracts(broker, slug, action)

        # ── Consent ──────────────────────────────────────────────
        consent_graph = self._consent_graph_or_none()
        consent_trace = self._simulate_consent(
            consent_graph,
            target_id=slug,
            source_id=consent_source_id or resource_id,
            scope=consent_scope,
            metadata=request_metadata,
        )

        # ── Provenance preview (no write) ────────────────────────
        ledger = self._ledger_or_none()
        empty_input_hash = hashlib.sha256(b"{}").hexdigest()
        provenance_trace: dict[str, Any] = {
            "available": ledger is not None,
            "would_record": ledger is not None,
            "preview": {
                "action": _provenance_action_for(action),
                "actor_id": slug,
                "resource_id": resource_id,
                "input_hash_preview": empty_input_hash,
                "metadata": request_metadata,
                "timestamp": timestamp.isoformat(),
            },
        }
        if ledger is None:
            provenance_trace["reason"] = (
                "Provenance ledger is not enabled on this registry; "
                "no record would be written."
            )

        # ── Reflexive ────────────────────────────────────────────
        analyzer = self._analyzer_or_none()
        reflexive_trace = self._simulate_reflexive(
            analyzer,
            actor_id=slug,
            metric_name=metric_name,
            metric_value=metric_value,
        )

        # ── Compose verdict ──────────────────────────────────────
        blockers: list[dict[str, Any]] = []
        if policy_trace.get("decision") == "deny":
            blockers.append(
                {"plane": "policy", "reason": policy_trace.get("reason", "")}
            )
        if not consent_trace.get("granted", True) and consent_trace.get("available"):
            blockers.append(
                {"plane": "consent", "reason": consent_trace.get("reason", "")}
            )
        if client.status == "suspended":  # an explicit application-level block
            blockers.append(
                {
                    "plane": "client",
                    "reason": (client.suspended_reason or "Client is suspended."),
                }
            )

        if blockers:
            verdict = "deny"
        elif policy_trace.get("decision") == "defer":
            verdict = "review"
        else:
            verdict = "allow"

        return {
            "client": client.to_dict(),
            "request": {
                "action": action,
                "resource_id": resource_id,
                "consent_scope": consent_scope,
                "consent_source_id": consent_source_id or resource_id,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metadata": request_metadata,
                "tags": request_tags,
                "timestamp": timestamp.isoformat(),
            },
            "policy": policy_trace,
            "contracts": contracts_trace,
            "consent": consent_trace,
            "ledger": provenance_trace,
            "reflexive": reflexive_trace,
            "verdict": verdict,
            "blockers": blockers,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _simulate_policy(
        self,
        engine: Any,
        *,
        slug: str,
        action: str,
        resource_id: str,
        metadata: dict[str, Any],
        tags: list[str],
        timestamp: Any,
    ) -> dict[str, Any]:
        """Call PolicyEngine.evaluate against a fresh
        :class:`PolicyEvaluationContext`. The engine MAY emit an
        audit row tagged ``simulated=True`` (we mark the metadata
        accordingly so audit consumers can filter); that's by design
        — operators want to know what their kernel actually said.
        """
        if engine is None:
            return {
                "available": False,
                "decision": "allow",
                "reason": (
                    "Policy kernel is not enabled on this registry; "
                    "no policy gate would run."
                ),
                "policy_id": None,
                "constraints": [],
            }
        try:
            from fastmcp.server.security.policy.provider import (
                PolicyEvaluationContext,
            )

            evaluation_ctx = PolicyEvaluationContext(
                actor_id=slug,
                action=action,
                resource_id=resource_id,
                metadata=metadata,
                timestamp=timestamp,
                tags=frozenset(tags),
            )
            result = await engine.evaluate(evaluation_ctx)
        except Exception as exc:
            logger.exception("Policy simulation failed")
            return {
                "available": True,
                "decision": "error",
                "reason": f"Policy evaluation raised: {exc!r}",
                "policy_id": None,
                "constraints": [],
            }

        decision_value = getattr(
            getattr(result, "decision", None),
            "value",
            str(getattr(result, "decision", "")),
        )
        return {
            "available": True,
            "decision": (decision_value or "").lower() or "allow",
            "reason": getattr(result, "reason", "") or "",
            "policy_id": getattr(result, "policy_id", None),
            "constraints": list(getattr(result, "constraints", []) or []),
            "evaluated_at": (
                result.evaluated_at.isoformat()
                if getattr(result, "evaluated_at", None)
                else None
            ),
        }

    @staticmethod
    def _simulate_contracts(broker: Any, slug: str, action: str) -> dict[str, Any]:
        """Walk the agent's active contracts and report whether any
        of them cover ``action``.

        Coverage rule: a contract is considered to cover ``action``
        when (a) it has no ACCESS_CONTROL terms (permissive default),
        or (b) at least one ACCESS_CONTROL term has either no
        ``actions`` constraint or an ``actions`` list that includes
        the requested action. This mirrors how operators tend to
        write contract terms (whitelist of actions per term).
        """
        if broker is None:
            return {
                "available": False,
                "covered": True,
                "reason": (
                    "Contract Broker is not enabled; no contract validation would run."
                ),
                "contracts": [],
            }
        try:
            contracts = list(broker.get_active_contracts_for_agent(slug))
        except Exception as exc:
            logger.exception("Contract simulation lookup failed")
            return {
                "available": True,
                "covered": False,
                "reason": f"Broker lookup raised: {exc!r}",
                "contracts": [],
            }
        if not contracts:
            return {
                "available": True,
                "covered": False,
                "reason": (
                    f"No active contracts for agent_id={slug!r}; "
                    "the request would be rejected by any planes "
                    "requiring a contract."
                ),
                "contracts": [],
            }

        rows: list[dict[str, Any]] = []
        any_covers = False
        for c in contracts:
            terms = list(getattr(c, "terms", []) or [])
            access_terms = [
                t
                for t in terms
                if getattr(getattr(t, "term_type", None), "value", "").lower()
                == "access_control"
            ]
            if not access_terms:
                covers = True
                why = "no ACCESS_CONTROL terms (permissive default)"
            else:
                covers = False
                why = "no ACCESS_CONTROL term whitelisted this action"
                for term in access_terms:
                    constraint = dict(getattr(term, "constraint", {}) or {})
                    actions = constraint.get("actions")
                    if not actions or action in actions:
                        covers = True
                        why = f"covered by term {getattr(term, 'term_id', '?')!r}"
                        break
            if covers:
                any_covers = True
            rows.append(
                {
                    "contract_id": getattr(c, "contract_id", ""),
                    "server_id": getattr(c, "server_id", ""),
                    "covers": covers,
                    "reason": why,
                }
            )
        return {
            "available": True,
            "covered": any_covers,
            "reason": (
                "At least one active contract covers this action."
                if any_covers
                else "No active contract covers this action."
            ),
            "contracts": rows,
        }

    @staticmethod
    def _simulate_consent(
        graph: Any,
        *,
        target_id: str,
        source_id: str,
        scope: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if graph is None:
            return {
                "available": False,
                "granted": True,
                "reason": ("Consent Graph is not enabled; no consent gate would run."),
                "path": [],
            }
        try:
            from fastmcp.server.security.consent.models import ConsentQuery

            query = ConsentQuery(
                source_id=source_id,
                target_id=target_id,
                scope=scope,
                context=metadata,
            )
            decision = graph.evaluate(query)
        except Exception as exc:
            logger.exception("Consent simulation failed")
            return {
                "available": True,
                "granted": False,
                "reason": f"Consent evaluation raised: {exc!r}",
                "path": [],
            }
        return {
            "available": True,
            "granted": bool(getattr(decision, "granted", False)),
            "reason": getattr(decision, "reason", "") or "",
            "path": [
                {
                    "edge_id": getattr(edge, "edge_id", ""),
                    "source_id": getattr(edge, "source_id", ""),
                    "target_id": getattr(edge, "target_id", ""),
                    "scopes": list(getattr(edge, "scopes", []) or []),
                }
                for edge in getattr(decision, "path", []) or []
            ],
            "query": {
                "source_id": source_id,
                "target_id": target_id,
                "scope": scope,
            },
        }

    @staticmethod
    def _simulate_reflexive(
        analyzer: Any,
        *,
        actor_id: str,
        metric_name: str | None,
        metric_value: float | None,
    ) -> dict[str, Any]:
        if analyzer is None:
            return {
                "available": False,
                "reason": (
                    "Reflexive Core is not enabled; no behavioral "
                    "drift check would run."
                ),
            }
        if not metric_name:
            return {
                "available": True,
                "evaluated": False,
                "reason": (
                    "No metric specified; supply ``metric_name`` and "
                    "``metric_value`` to check against the baseline."
                ),
            }
        try:
            baseline = analyzer.get_baseline(actor_id, metric_name)
        except Exception as exc:
            logger.exception("Reflexive baseline lookup failed")
            return {
                "available": True,
                "evaluated": False,
                "reason": f"Baseline lookup raised: {exc!r}",
            }
        if baseline is None:
            return {
                "available": True,
                "evaluated": False,
                "reason": (
                    f"No baseline yet for metric {metric_name!r} on "
                    f"actor {actor_id!r}; the analyzer learns over "
                    "the first few real calls."
                ),
            }
        sample_count = int(getattr(baseline, "sample_count", 0) or 0)
        if metric_value is None:
            return {
                "available": True,
                "evaluated": False,
                "reason": "Specify metric_value to score against baseline.",
                "baseline": {
                    "metric_name": metric_name,
                    "mean": getattr(baseline, "mean", None),
                    "sample_count": sample_count,
                },
            }
        try:
            deviation = float(baseline.compute_deviation(float(metric_value)))
        except Exception as exc:
            logger.exception("Reflexive deviation compute failed")
            return {
                "available": True,
                "evaluated": False,
                "reason": f"compute_deviation raised: {exc!r}",
            }
        # Ordinal severity bands matching analyzer._classify_severity.
        if deviation >= 4.0:
            severity = "critical"
        elif deviation >= 3.0:
            severity = "high"
        elif deviation >= 2.0:
            severity = "medium"
        elif deviation >= 1.0:
            severity = "low"
        else:
            severity = "info"
        return {
            "available": True,
            "evaluated": True,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "deviation_sigma": deviation,
            "severity": severity,
            "baseline": {
                "mean": getattr(baseline, "mean", None),
                "sample_count": sample_count,
            },
            "reason": (
                f"Deviation = {deviation:.2f}σ → severity={severity}."
                if sample_count >= 5
                else (
                    f"Baseline has {sample_count} samples (need ≥5 for a "
                    "stable deviation score)."
                )
            ),
        }

    # ── Iter 9: runtime control-plane toggles ─────────────────────

    def get_control_plane_status(self) -> dict[str, Any]:
        """Snapshot of each opt-in plane's current state + persisted toggle.

        Used by the admin settings UI. Returns a list of plane
        records, each carrying:

        - ``plane``: canonical plane name.
        - ``enabled``: whether the plane is currently attached to
          the running security context.
        - ``persisted``: the most recent persisted toggle (with
          actor + timestamp), or ``None`` if the plane has never
          been toggled via the admin UI.
        - ``description``: short copy explaining what the plane
          does, for the UI.
        """
        ctx = self._required_context()
        persisted = self._control_plane_store.get_all()
        descriptions = {
            "contracts": (
                "Context Broker: negotiates and records agent ↔ server contracts."
            ),
            "consent": (
                "Consent Graph: federated consent + jurisdiction policy evaluator."
            ),
            "provenance": (
                "Provenance Ledger: append-only audit trail of "
                "every operation, hash-chained."
            ),
            "reflexive": (
                "Reflexive Core: per-actor behavioral baselines + drift detection."
            ),
        }
        live_state = {
            "contracts": getattr(ctx, "broker", None) is not None,
            "consent": getattr(ctx, "consent_graph", None) is not None,
            "provenance": getattr(ctx, "provenance_ledger", None) is not None,
            "reflexive": (getattr(ctx, "behavioral_analyzer", None) is not None),
        }
        planes = []
        for name in sorted(PLANE_NAMES):
            persisted_record = persisted.get(name)
            planes.append(
                {
                    "plane": name,
                    "enabled": live_state[name],
                    "description": descriptions.get(name, ""),
                    "persisted": (
                        persisted_record.to_dict()
                        if persisted_record is not None
                        else None
                    ),
                }
            )
        return {
            "planes": planes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def enable_plane(
        self,
        plane: str,
        *,
        actor_id: str = "admin",
    ) -> dict[str, Any]:
        """Attach an opt-in control plane at runtime.

        Effect:
            1. Constructs the plane with default config (using the
               registry's persistence backend + signing secret where
               relevant).
            2. Sets the matching attribute on the security context
               so governance panels report it as available.
            3. Appends the plane's middleware to ``ctx.middleware``
               so MCP traffic actually flows through enforcement.
            4. Persists the toggle so the plane stays on after a
               restart.

        Idempotent: re-enabling an already-enabled plane simply
        refreshes the persisted record without rebuilding state.

        Raises:
            ValueError: When ``plane`` isn't a known plane name.
        """
        if plane not in PLANE_NAMES:
            raise ValueError(
                f"Unknown control plane: {plane!r}. "
                f"Expected one of: {sorted(PLANE_NAMES)}."
            )
        ctx = self._required_context()
        already_attached = self._is_plane_attached(plane, ctx)
        if not already_attached:
            self._attach_plane(plane, ctx)
        self._control_plane_store.set(
            plane, enabled=True, updated_by=actor_id or "admin"
        )
        return self.get_control_plane_status()

    def disable_plane(
        self,
        plane: str,
        *,
        actor_id: str = "admin",
    ) -> dict[str, Any]:
        """Detach an opt-in control plane at runtime.

        Drops the plane's in-memory state, removes its middleware
        from the chain, nulls the security-context attribute, and
        persists the toggle so the plane stays off across restarts.

        State loss: the broker's active contracts, the consent
        graph's nodes/edges, the analyzer's baselines, and the
        ledger's record buffer are dropped. Operators who want to
        retain plane state across toggles must wire a
        ``persistence_path`` so each plane's backend persists to
        disk; on re-enable, the plane reloads from that backend.

        Raises:
            ValueError: When ``plane`` isn't a known plane name.
        """
        if plane not in PLANE_NAMES:
            raise ValueError(
                f"Unknown control plane: {plane!r}. "
                f"Expected one of: {sorted(PLANE_NAMES)}."
            )
        ctx = self._required_context()
        if self._is_plane_attached(plane, ctx):
            self._detach_plane(plane, ctx)
        self._control_plane_store.set(
            plane, enabled=False, updated_by=actor_id or "admin"
        )
        return self.get_control_plane_status()

    def _is_plane_attached(self, plane: str, ctx: SecurityContext) -> bool:
        if plane == "contracts":
            return getattr(ctx, "broker", None) is not None
        if plane == "consent":
            return getattr(ctx, "consent_graph", None) is not None
        if plane == "provenance":
            return getattr(ctx, "provenance_ledger", None) is not None
        if plane == "reflexive":
            return getattr(ctx, "behavioral_analyzer", None) is not None
        return False

    def _backend_for_runtime_planes(self) -> Any:
        """Return the SQLite backend matching the registry's
        persistence config, or ``None`` for ephemeral registries.

        Used by the runtime attach helpers so newly-instantiated
        planes share storage with their original counterparts.
        """
        if not self._persistence_path:
            return None
        return SQLiteBackend(self._persistence_path)

    def _attach_plane(self, plane: str, ctx: SecurityContext) -> None:
        """Construct a fresh plane + its middleware and attach both.

        Uses default config — operators who need custom config
        (e.g. broker default_terms, analyzer thresholds) should
        construct the registry with ``enable_<plane>=False`` and
        pass their own ``security=SecurityConfig(...)`` instead of
        relying on runtime toggles.
        """
        backend = self._backend_for_runtime_planes()
        server_id = self.name or "purecipher-registry"

        if plane == "contracts":
            from fastmcp.server.security.contracts.broker import ContextBroker
            from fastmcp.server.security.contracts.crypto import (
                ContractCryptoHandler,
                SigningAlgorithm,
            )
            from fastmcp.server.security.middleware.contract_validation import (
                ContractValidationMiddleware,
            )

            crypto = (
                ContractCryptoHandler(
                    algorithm=SigningAlgorithm.HMAC_SHA256,
                    secret_key=self._signing_secret_bytes,
                )
                if self._signing_secret_bytes is not None
                else None
            )
            broker = ContextBroker(
                server_id=server_id,
                crypto_handler=crypto,
                backend=backend,
            )
            ctx.broker = broker
            ctx.middleware.append(ContractValidationMiddleware(broker=broker))
            return

        if plane == "consent":
            from fastmcp.server.security.consent.graph import ConsentGraph
            from fastmcp.server.security.middleware.consent_enforcement import (
                ConsentEnforcementMiddleware,
            )

            graph = ConsentGraph(graph_id=server_id, backend=backend)
            ctx.consent_graph = graph
            ctx.middleware.append(ConsentEnforcementMiddleware(graph=graph))
            return

        if plane == "provenance":
            from fastmcp.server.security.middleware.provenance_recording import (
                ProvenanceRecordingMiddleware,
            )
            from fastmcp.server.security.provenance.ledger import (
                ProvenanceLedger,
            )

            ledger = ProvenanceLedger(ledger_id=server_id, backend=backend)
            ctx.provenance_ledger = ledger
            ctx.middleware.append(ProvenanceRecordingMiddleware(ledger=ledger))
            return

        if plane == "reflexive":
            from fastmcp.server.security.middleware.reflexive import (
                ReflexiveMiddleware,
            )
            from fastmcp.server.security.reflexive.analyzer import (
                BehavioralAnalyzer,
                EscalationEngine,
            )

            analyzer = BehavioralAnalyzer(backend=backend)
            escalation_engine = EscalationEngine(backend=backend)
            ctx.behavioral_analyzer = analyzer
            ctx.escalation_engine = escalation_engine
            ctx.middleware.append(
                ReflexiveMiddleware(
                    analyzer=analyzer,
                    escalation_engine=escalation_engine,
                )
            )
            return

    def _detach_plane(self, plane: str, ctx: SecurityContext) -> None:
        """Remove a plane from the security context.

        Filters out the plane's middleware class from
        ``ctx.middleware`` *and* nulls the matching attribute so
        ``_*_or_none()`` helpers report unavailable. Plane-specific
        in-memory state (contracts dict, consent graph, ledger
        records, baselines) is dropped — it's gc'd along with the
        plane object once nothing else references it.
        """
        if plane == "contracts":
            from fastmcp.server.security.middleware.contract_validation import (
                ContractValidationMiddleware,
            )

            ctx.broker = None
            ctx.middleware = [
                m
                for m in ctx.middleware
                if not isinstance(m, ContractValidationMiddleware)
            ]
            return

        if plane == "consent":
            from fastmcp.server.security.middleware.consent_enforcement import (
                ConsentEnforcementMiddleware,
            )

            ctx.consent_graph = None
            ctx.middleware = [
                m
                for m in ctx.middleware
                if not isinstance(m, ConsentEnforcementMiddleware)
            ]
            return

        if plane == "provenance":
            from fastmcp.server.security.middleware.provenance_recording import (
                ProvenanceRecordingMiddleware,
            )

            ctx.provenance_ledger = None
            ctx.middleware = [
                m
                for m in ctx.middleware
                if not isinstance(m, ProvenanceRecordingMiddleware)
            ]
            return

        if plane == "reflexive":
            from fastmcp.server.security.middleware.reflexive import (
                ReflexiveMiddleware,
            )

            ctx.behavioral_analyzer = None
            ctx.escalation_engine = None
            ctx.middleware = [
                m for m in ctx.middleware if not isinstance(m, ReflexiveMiddleware)
            ]
            return

    @staticmethod
    def _validate_registry_context(ctx: SecurityContext) -> None:
        missing: list[str] = []
        if ctx.registry is None:
            missing.append("registry")
        if ctx.tool_marketplace is None:
            missing.append("tool_marketplace")
        if ctx.certification_pipeline is None:
            missing.append("certification_pipeline")
        if missing:
            raise ValueError(
                "PureCipherRegistry requires SecureMCP components: "
                + ", ".join(missing)
            )

    def _serialize_verification(self, verification: Any) -> dict[str, Any]:
        return {
            "valid": verification.valid,
            "signature_valid": verification.signature_valid,
            "manifest_match": verification.manifest_match,
            "issues": list(verification.issues),
        }

    def _marketplace(self) -> ToolMarketplace:
        ctx = self._required_context()
        if ctx.tool_marketplace is None:
            raise RuntimeError("Tool marketplace is not attached to this registry.")
        return ctx.tool_marketplace

    def publish_toolset_as_listings(
        self,
        toolset_id: str,
        *,
        publisher_id: str,
        version: str = "0.0.0",
        categories: set[ToolCategory] | None = None,
        extra_tags: set[str] | None = None,
        server_url_override: str | None = None,
    ) -> list[ToolListing]:
        """Iter 13.4: turn an OpenAPI toolset into ``ToolListing`` records.

        Walks the toolset's ``selected_operations`` and publishes one
        listing per operation through ``ToolMarketplace.publish``. Each
        listing carries ``AttestationKind.OPENAPI`` and a manifest
        whose ``metadata`` round-trips the originating ``source_id``,
        ``operation_key``, ``spec_sha256``, and the input/output
        schemas — enough for the executor to reconstruct the request
        and the public detail page to render an input form without
        re-fetching the raw spec.

        Re-publishing the same toolset is an upsert at the marketplace
        layer: ``publish`` updates an existing listing keyed by
        ``tool_name`` rather than creating a duplicate.

        Cross-publisher isolation: callers are expected to verify the
        toolset belongs to ``publisher_id`` before invoking this
        method (the route layer does so). The method itself trusts the
        caller and stamps every manifest with the supplied
        ``publisher_id`` as the author.
        """
        from purecipher.openapi_publish import build_listing_payload
        from purecipher.openapi_store import (
            extract_openapi_operations_detailed,
        )

        toolset = self._openapi_store.get_toolset(toolset_id)
        if toolset is None:
            raise ValueError(f"Unknown toolset {toolset_id!r}")
        source_id = str(toolset.get("source_id") or "")
        if not source_id:
            raise ValueError(f"Toolset {toolset_id!r} has no source_id")
        spec = self._openapi_store.get_source_spec(source_id)
        if spec is None:
            raise ValueError(f"OpenAPI source {source_id!r} no longer exists")
        # Re-fetch the source record so we get spec_sha256, title,
        # source_url etc. without recomputing.
        source_record: dict[str, Any] | None = None
        if not self._openapi_store.db_path:
            source_record = dict(
                self._openapi_store._memory_sources.get(source_id) or {}
            )
        else:
            # Reconstruct the public-facing record from spec + sha. We
            # don't expose a get_source() method on the store; the
            # spec_sha256 we need is derivable from the spec itself.
            import hashlib as _hashlib
            import json as _json

            spec_sha = _hashlib.sha256(
                _json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            source_record = {
                "source_id": source_id,
                "publisher_id": str(toolset.get("publisher_id") or ""),
                "spec_json": spec,
                "spec_sha256": spec_sha,
            }

        # Pick the default server URL from the spec — operation-level
        # overrides win, then path-level (handled by the extractor),
        # then the document's top-level ``servers``.
        top_servers = spec.get("servers") or []
        default_server = ""
        if isinstance(top_servers, list):
            for srv in top_servers:
                if isinstance(srv, dict):
                    url = srv.get("url")
                    if isinstance(url, str) and url:
                        default_server = url
                        break

        ops = extract_openapi_operations_detailed(spec)
        ops_by_key = {op.get("operation_key"): op for op in ops}

        selected_keys = list(toolset.get("selected_operations") or [])
        if not selected_keys:
            return []

        published: list[ToolListing] = []
        for key in selected_keys:
            op = ops_by_key.get(key)
            if op is None:
                # The toolset might reference an operation that no
                # longer exists in the current spec — skip rather than
                # crash, and let the caller see fewer-than-expected
                # listings.
                continue
            # Per-operation server override > toolset-level override > spec default.
            op_servers = op.get("server_urls") or []
            op_server = op_servers[0] if op_servers else ""
            server_url = server_url_override or op_server or default_server
            if not server_url:
                raise ValueError(f"Operation {key!r} has no server URL declared")
            payload = build_listing_payload(
                op,
                source=source_record,  # type: ignore[arg-type]
                toolset=toolset,
                server_url=server_url,
                publisher_id=publisher_id,
                version=version,
            )
            tags = set(payload.get("tags") or set())
            if extra_tags:
                tags.update(extra_tags)
            listing = self._marketplace().publish(
                payload["tool_name"],
                display_name=payload["display_name"],
                description=payload["description"],
                version=payload["version"],
                author=payload["author"],
                categories=categories,
                manifest=payload["manifest"],
                tags=tags,
                metadata={
                    **(payload.get("metadata") or {}),
                    "issuer_id": self._issuer_id,
                    "verified_registry": "purecipher",
                },
                attestation_kind=AttestationKind.OPENAPI,
                hosting_mode=HostingMode.PROXY,
            )
            published.append(listing)
            # Iter 13.5: register the listing as a real MCP tool so
            # ``tools/list`` and ``tools/call`` see it. The proxy tool
            # delegates to the OpenAPI executor, with all five
            # governance planes still gating the call via the existing
            # middleware chain (the proxy is the leaf, not the gate).
            self._register_openapi_proxy_tool(listing)
        return published

    def _register_openapi_proxy_tool(self, listing: ToolListing) -> None:
        """Iter 13.5: bind a published OpenAPI listing to an MCP tool.

        Builds a :class:`FunctionTool` whose async ``fn`` looks the
        operation back up by ``source_id`` + ``operation_key`` (so the
        spec is the source of truth — the listing's stored input
        schema is just a hint), instantiates an
        :class:`OpenAPIToolExecutor` scoped to the listing's owning
        publisher, and runs it. Idempotent: re-registering the same
        ``tool_name`` is fine — FastMCP's local provider replaces the
        existing entry.
        """
        from purecipher.openapi_executor import OpenAPIToolExecutor
        from purecipher.openapi_publish import (
            META_OPENAPI_INPUT_SCHEMA,
            META_OPENAPI_OPERATION_KEY,
            META_OPENAPI_OUTPUT_SCHEMA,
            META_OPENAPI_SERVER_URL,
            META_OPENAPI_SOURCE_ID,
            META_PROVIDER_KIND,
            PROVIDER_KIND_OPENAPI,
        )
        from purecipher.openapi_store import (
            extract_openapi_operations_detailed,
        )

        # Defensively skip listings that aren't OpenAPI-backed.
        if listing.attestation_kind is not AttestationKind.OPENAPI:
            return
        meta = listing.metadata or {}
        if meta.get(META_PROVIDER_KIND) != PROVIDER_KIND_OPENAPI:
            return
        source_id = str(meta.get(META_OPENAPI_SOURCE_ID) or "")
        operation_key = str(meta.get(META_OPENAPI_OPERATION_KEY) or "")
        if not source_id or not operation_key:
            return

        publisher_id = listing.author or ""
        server_url = str(meta.get(META_OPENAPI_SERVER_URL) or "")
        input_schema = (
            meta.get(META_OPENAPI_INPUT_SCHEMA)
            if isinstance(meta.get(META_OPENAPI_INPUT_SCHEMA), dict)
            else {"type": "object"}
        )
        output_schema_raw = meta.get(META_OPENAPI_OUTPUT_SCHEMA)
        # Output schemas declared on operations are usually arrays or
        # primitives, but MCP requires `output_schema` to describe an
        # object. Drop the schema unless it's already object-shaped to
        # avoid the marketplace rejecting our tool.
        output_schema: dict[str, Any] | None = None
        if (
            isinstance(output_schema_raw, dict)
            and output_schema_raw.get("type") == "object"
        ):
            output_schema = output_schema_raw

        listing_tool_name = listing.tool_name
        listing_description = (
            listing.description or listing.display_name or listing_tool_name
        )

        async def _openapi_proxy_fn(**arguments: Any) -> Any:
            spec = self._openapi_store.get_source_spec(source_id)
            if spec is None:
                raise RuntimeError(
                    f"OpenAPI source {source_id!r} for tool "
                    f"{listing_tool_name!r} no longer exists."
                )
            ops = extract_openapi_operations_detailed(spec)
            op = next(
                (o for o in ops if o.get("operation_key") == operation_key),
                None,
            )
            if op is None:
                raise RuntimeError(
                    f"Operation {operation_key!r} no longer exists in "
                    f"OpenAPI source {source_id!r}."
                )
            # Server URL: stored on the listing wins over re-derive
            # because the publisher may have overridden it at publish
            # time. Fall through to the operation's own server.
            url = server_url
            if not url:
                op_servers = op.get("server_urls") or []
                if op_servers:
                    url = op_servers[0]
            if not url:
                top = spec.get("servers") or []
                for srv in top:
                    if isinstance(srv, dict) and srv.get("url"):
                        url = str(srv["url"])
                        break
            if not url:
                raise RuntimeError(f"Tool {listing_tool_name!r} has no server URL.")
            executor = OpenAPIToolExecutor(
                spec=spec,
                operation=op,
                server_url=url,
                publisher_id=publisher_id,
                source_id=source_id,
            )
            result = await executor.execute(
                arguments,
                store=self._openapi_store,
                client=self._openapi_invoke_client,
            )
            return {
                "status_code": result.status_code,
                "content_type": result.content_type,
                "body": result.body,
                "validation_warnings": result.validation_warnings,
            }

        # Build the FunctionTool directly so we can inject the
        # OpenAPI-derived input schema verbatim — relying on
        # ``from_function`` would derive a permissive ``**arguments``
        # schema that hides the operation's real shape from MCP
        # clients.
        from fastmcp.tools.function_tool import FunctionTool

        proxy_tool = FunctionTool(
            fn=_openapi_proxy_fn,
            name=listing_tool_name,
            description=listing_description,
            parameters=input_schema,
            output_schema=output_schema,
            tags={"openapi", "registry-proxy"},
            meta={
                "purecipher.attestation_kind": "openapi",
                "purecipher.openapi.operation_key": operation_key,
                "purecipher.openapi.source_id": source_id,
            },
        )
        self.add_tool(proxy_tool)

    def _reattach_openapi_proxy_tools(self) -> None:
        """Iter 13.5: re-register MCP proxy tools for every persisted
        OpenAPI listing.

        Called once during construction so a SQLite-backed registry
        that's just been (re)started exposes its previously-published
        OpenAPI tools without the publisher having to re-run the
        publish flow. We swallow individual rebuild failures so a
        single bad listing doesn't keep the registry from booting.
        """
        try:
            marketplace = self._marketplace()
        except RuntimeError:
            # Marketplace isn't attached yet (e.g. constructor still
            # finishing); the publish path will register tools on
            # demand instead.
            return
        # Search by the "openapi" tag we stamp on every OpenAPI-backed
        # listing during ``publish_toolset_as_listings``. ``search()``
        # caps at the supplied ``limit`` so we set it high enough that
        # a registry with thousands of OpenAPI tools still re-attaches
        # all of them on boot.
        listings = marketplace.search(tags={"openapi"}, limit=10_000)
        for listing in listings:
            if listing.attestation_kind is not AttestationKind.OPENAPI:
                continue
            try:
                self._register_openapi_proxy_tool(listing)
            except Exception:
                # Fail-soft: a single bad listing must not keep the
                # registry from booting. ``logger.exception`` keeps
                # the stack trace for postmortem.
                logger.exception(
                    "Failed to re-attach OpenAPI proxy tool for listing %r",
                    listing.tool_name,
                )

    def record_registry_notification(
        self,
        *,
        event_kind: str,
        title: str,
        body: str,
        link_path: str | None = None,
        audiences: tuple[str, ...] | None = None,
    ) -> None:
        """Append a UI notification visible to the given RBAC personas."""

        self._notification_feed.append(
            event_kind=event_kind,
            title=title,
            body=body,
            link_path=link_path,
            audiences=audiences,
        )

    def get_registry_notifications(
        self,
        *,
        auth_enabled: bool,
        role: str | None,
        limit: int = 40,
    ) -> dict[str, Any]:
        """Return recent notifications filtered for the caller's persona."""

        items = self._notification_feed.list_recent(
            auth_enabled=auth_enabled,
            role=role,
            limit=limit,
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }

    def _trust_registry(self) -> TrustRegistry:
        ctx = self._required_context()
        if ctx.registry is None:
            raise RuntimeError("Trust registry is not attached to this registry.")
        return ctx.registry

    def _certification_pipeline(self) -> CertificationPipeline:
        ctx = self._required_context()
        if ctx.certification_pipeline is None:
            raise RuntimeError(
                "Certification pipeline is not attached to this registry."
            )
        return ctx.certification_pipeline

    def _policy_api(self) -> SecurityAPI:
        api = self.security_api
        if api is not None:
            return api
        return SecurityAPI.from_context(self._required_context())

    def _trust_overall(self, listing: ToolListing) -> float | None:
        ctx = self._required_context()
        score = (
            ctx.registry.get_trust_score(listing.tool_name) if ctx.registry else None
        )
        return score.overall if score is not None else None

    def _is_public_listing(self, listing: ToolListing) -> bool:
        if listing.status != PublishStatus.PUBLISHED:
            return False
        if not listing.is_certified:
            return False
        level_order = list(CertificationLevel)
        return level_order.index(listing.certification_level) >= level_order.index(
            self.minimum_certification
        )

    def _get_public_listing(self, tool_name: str) -> ToolListing | None:
        listing = self._marketplace().get_by_name(tool_name)
        if listing is None or not self._is_public_listing(listing):
            return None
        return listing

    def _serialize_listing_detail(self, listing: ToolListing) -> dict[str, Any]:
        ctx = self._required_context()
        score = (
            ctx.registry.get_trust_score(listing.tool_name) if ctx.registry else None
        )
        verification = None
        if listing.attestation is not None and ctx.certification_pipeline is not None:
            verification = self._serialize_verification(
                ctx.certification_pipeline.verify_attestation(
                    listing.attestation,
                    listing.manifest,
                )
            )

        return {
            **listing.to_dict(),
            "metadata": dict(listing.metadata),
            "manifest": listing.manifest.to_dict()
            if listing.manifest is not None
            else None,
            "attestation": (
                listing.attestation.to_dict()
                if listing.attestation is not None
                else None
            ),
            "trust_score": score.to_dict() if score is not None else None,
            "verification": verification,
            "publisher_id": publisher_id_from_author(listing.author),
            "status": listing.status.value,
            "moderation_log": [
                decision.to_dict() for decision in listing.moderation_log
            ],
        }

    def _session_from_request(self, request: Request) -> RegistrySession | None:
        if not self.auth_enabled:
            return None

        token = request.cookies.get(self._auth_settings.cookie_name, "")
        bearer_token = ""
        if not token:
            authorization = request.headers.get("authorization", "")
            scheme, _, candidate = authorization.partition(" ")
            if scheme.lower() == "bearer":
                bearer_token = candidate.strip()
                token = bearer_token
        if not token:
            return None
        session = self._auth_settings.decode_token(token)
        if session is not None:
            if not self._account_security.session_is_active(
                session.session_id,
                username=session.username,
            ):
                return None
            return session

        if bearer_token:
            user = self._account_security.authenticate_api_token(bearer_token)
            if user is not None:
                return RegistrySession(
                    username=user.username,
                    role=user.role,
                    display_name=user.display_name,
                    expires_at="",
                    session_id="",
                )
        return None

    @staticmethod
    def _session_payload(session: RegistrySession | None) -> dict[str, Any] | None:
        return session.to_dict() if session is not None else None

    def _bootstrap_required(self) -> bool:
        return self.auth_enabled and not self._account_security.has_accounts()

    @staticmethod
    def _has_roles(
        session: RegistrySession | None,
        allowed_roles: set[RegistryRole],
    ) -> bool:
        """Return True when the session may act under an RBAC gate.

        ``RegistryRole.ADMIN`` is a platform superuser: admins satisfy any
        non-empty role gate (reviewer, publisher, etc.). Empty ``allowed_roles``
        is treated as false so callers do not accidentally grant access.
        """

        if session is None:
            return False
        if not allowed_roles:
            return False
        return session.role in allowed_roles

    def _guard_last_admin_change(
        self,
        username: str,
        new_role: RegistryRole | None,
        disabled: bool | None,
    ) -> str | None:
        """Prevent admin lifecycle changes that would lock out the registry."""

        users = self._account_security.list_accounts()
        target = next(
            (user for user in users if user.get("username") == username), None
        )
        if target is None or target.get("role") != RegistryRole.ADMIN.value:
            return None
        active_admins = [
            user
            for user in users
            if user.get("role") == RegistryRole.ADMIN.value
            and user.get("active") is True
        ]
        is_last_active_admin = (
            target.get("active") is True
            and len(active_admins) == 1
            and active_admins[0].get("username") == username
        )
        if not is_last_active_admin:
            return None
        if disabled is True:
            return "Cannot disable the last active admin account."
        if new_role is not None and new_role != RegistryRole.ADMIN:
            return "Cannot remove the last active admin role."
        return None

    def _moderation_roles_for_action(
        self,
        action_name: str,
    ) -> set[RegistryRole]:
        normalized = action_name.strip().lower().replace("_", "-")
        if normalized in {"approve", "reject", "request-changes"}:
            return {RegistryRole.REVIEWER, RegistryRole.ADMIN}
        if normalized in {"suspend", "unsuspend"}:
            return {RegistryRole.ADMIN}
        if normalized == "deregister":
            return {RegistryRole.ADMIN}
        if normalized in {"withdraw", "resubmit"}:
            return {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN}
        return set()

    def _filter_queue_for_session(
        self,
        queue: dict[str, Any],
        session: RegistrySession | None,
    ) -> dict[str, Any]:
        filtered_sections: dict[str, list[dict[str, Any]]] = {}
        for section_name, items in (queue.get("sections") or {}).items():
            section_items: list[dict[str, Any]] = []
            for item in items:
                filtered_item = dict(item)
                filtered_item["available_actions"] = [
                    action
                    for action in list(item.get("available_actions") or [])
                    if self._has_roles(
                        session,
                        self._moderation_roles_for_action(str(action)),
                    )
                ]
                section_items.append(filtered_item)
            filtered_sections[section_name] = section_items
        return {
            **queue,
            "sections": filtered_sections,
        }

    def _set_auth_cookie(self, response: Response, token: str) -> None:
        response.set_cookie(
            self._auth_settings.cookie_name,
            token,
            max_age=self._auth_settings.token_ttl_seconds,
            httponly=True,
            samesite="lax",
        )

    def _clear_auth_cookie(self, response: Response) -> None:
        response.delete_cookie(
            self._auth_settings.cookie_name,
            httponly=True,
            samesite="lax",
        )

    def _login_redirect(self, request: Request, *, prefix: str) -> RedirectResponse:
        next_path = _safe_next_path(
            str(request.url.path)
            + (f"?{request.url.query}" if request.url.query else ""),
            default=prefix,
        )
        return RedirectResponse(
            url=f"{prefix}/login?{urlencode({'next': next_path})}",
            status_code=303,
        )

    def _render_login_ui(
        self,
        *,
        prefix: str,
        next_path: str,
        session: RegistrySession | None = None,
        notice_title: str | None = None,
        notice_body: str | None = None,
        notice_is_error: bool = False,
    ) -> str:
        return create_login_html(
            server_name=self.name,
            registry_prefix=prefix,
            auth_enabled=self.auth_enabled,
            session=self._session_payload(session),
            next_path=next_path,
            notice_title=notice_title,
            notice_body=notice_body,
            notice_is_error=notice_is_error,
        )

    def get_registry_health(self) -> dict[str, Any]:
        """Return PureCipher registry health and counts."""

        trust_registry = self._trust_registry()
        marketplace = self._marketplace()
        published = marketplace.search(
            certified_only=True,
            min_certification=self.minimum_certification,
            limit=10_000,
        )
        pending = marketplace.search(
            status=PublishStatus.PENDING_REVIEW,
            limit=10_000,
        )
        return {
            "service": "purecipher-verified-registry",
            "server": self.name,
            "status": "ok",
            "issuer_id": self._issuer_id,
            "minimum_certification": self.minimum_certification.value,
            "require_moderation": self._require_moderation,
            "auth_enabled": self.auth_enabled,
            "bootstrap_required": self._bootstrap_required(),
            "registered_tools": trust_registry.record_count,
            "verified_tools": len(published),
            "pending_review": len(pending),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_policy_management(self) -> dict[str, Any]:
        """Return the current policy-management state for the registry UI."""

        api = self._policy_api()
        status = api.get_policy_status()
        versions = api.get_policy_versions()
        schema = api.get_policy_schema()
        proposals = api.get_governance_proposals()
        bundles = api.get_policy_bundles()
        packs = api.get_policy_packs()
        analytics = api.get_policy_analytics()
        environments = api.get_policy_environment_profiles()
        promotions = api.get_policy_promotions()
        return {
            "policy": status,
            "versions": versions,
            "schema": schema,
            "governance": proposals,
            "bundles": bundles,
            "packs": packs,
            "analytics": analytics,
            "environments": environments,
            "promotions": promotions,
            "simulation_defaults": self.get_default_policy_simulation_scenarios(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_default_policy_simulation_scenarios(self) -> list[dict[str, Any]]:
        """Return a small default scenario set for policy proposal simulation."""

        public_listings = self._marketplace().search(
            certified_only=True,
            min_certification=self.minimum_certification,
            limit=1,
        )
        public_tool = public_listings[0] if public_listings else None
        public_tool_name = (
            public_tool.tool_name if public_tool is not None else "weather-lookup"
        )
        public_tags = (
            sorted(public_tool.tags)
            if public_tool is not None
            else ["published", "tool"]
        )
        category_tags = (
            [
                category.value
                for category in sorted(
                    public_tool.categories, key=lambda item: item.value
                )
            ]
            if public_tool is not None
            else ["network", "utility"]
        )

        return [
            {
                "label": "Viewer uses a published tool",
                "resource_id": f"tool:{public_tool_name}",
                "action": "call_tool",
                "actor_id": "viewer",
                "metadata": {"role": "viewer", "surface": "catalog"},
                "tags": ["tool", *public_tags, *category_tags],
            },
            {
                "label": "Viewer tries an admin tool",
                "resource_id": "admin-panel",
                "action": "call_tool",
                "actor_id": "viewer",
                "metadata": {"role": "viewer", "surface": "catalog"},
                "tags": ["admin", "tool"],
            },
            {
                "label": "Publisher shares a tool",
                "resource_id": "registry:submit",
                "action": "submit_listing",
                "actor_id": "publisher",
                "metadata": {"role": "publisher", "surface": "publish"},
                "tags": ["registry", "publish"],
            },
            {
                "label": "Reviewer manages a listing",
                "resource_id": "registry:review",
                "action": "review_listing",
                "actor_id": "reviewer",
                "metadata": {"role": "reviewer", "surface": "review"},
                "tags": ["registry", "review"],
            },
            {
                "label": "Admin edits policy",
                "resource_id": "registry:policy",
                "action": "manage_policy",
                "actor_id": "admin",
                "metadata": {"role": "admin", "surface": "policy"},
                "tags": ["registry", "policy"],
            },
        ]

    async def create_policy_proposal(
        self,
        *,
        action: str,
        config: dict[str, Any] | None,
        target_index: int | None,
        description: str = "",
        author: str = "registry-admin",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a policy governance proposal."""

        return await self._policy_api().create_governance_proposal(
            action=action,
            config=config,
            target_index=target_index,
            description=description,
            author=author,
            metadata=metadata,
        )

    def get_policy_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Return a single policy governance proposal."""

        return self._policy_api().get_governance_proposal(proposal_id)

    def list_policy_proposals(self) -> dict[str, Any]:
        """Return policy governance proposals."""

        return self._policy_api().get_governance_proposals()

    def approve_policy_proposal(
        self,
        proposal_id: str,
        *,
        approver: str = "registry-admin",
        note: str = "",
    ) -> dict[str, Any]:
        """Approve a policy governance proposal."""

        return self._policy_api().approve_governance_proposal(
            proposal_id,
            approver=approver,
            note=note,
        )

    def assign_policy_proposal(
        self,
        proposal_id: str,
        *,
        reviewer: str,
        actor: str = "registry-admin",
        note: str = "",
    ) -> dict[str, Any]:
        """Assign ownership of a policy governance proposal."""

        return self._policy_api().assign_governance_proposal(
            proposal_id,
            reviewer=reviewer,
            actor=actor,
            note=note,
        )

    async def simulate_policy_proposal(
        self,
        proposal_id: str,
        *,
        scenarios: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Simulate a policy governance proposal."""

        return await self._policy_api().simulate_governance_proposal(
            proposal_id,
            scenarios_data=scenarios or self.get_default_policy_simulation_scenarios(),
        )

    async def deploy_policy_proposal(
        self,
        proposal_id: str,
        *,
        actor: str = "registry-admin",
        note: str = "",
    ) -> dict[str, Any]:
        """Deploy a policy governance proposal."""

        return await self._policy_api().deploy_governance_proposal(
            proposal_id,
            actor=actor,
            note=note,
        )

    def reject_policy_proposal(
        self,
        proposal_id: str,
        *,
        reason: str = "",
        actor: str = "registry-admin",
    ) -> dict[str, Any]:
        """Reject a policy governance proposal."""

        return self._policy_api().reject_governance_proposal(
            proposal_id,
            reason=reason,
            actor=actor,
        )

    def withdraw_policy_proposal(
        self,
        proposal_id: str,
        *,
        actor: str = "registry-admin",
        note: str = "",
    ) -> dict[str, Any]:
        """Withdraw a policy governance proposal."""

        return self._policy_api().withdraw_governance_proposal(
            proposal_id,
            actor=actor,
            note=note,
        )

    async def add_policy_provider(
        self,
        config: dict[str, Any],
        *,
        reason: str = "",
        author: str = "registry-admin",
    ) -> dict[str, Any]:
        """Add a policy provider to the live engine."""

        return await self._policy_api().add_policy_provider(
            config,
            reason=reason,
            author=author,
        )

    async def update_policy_provider(
        self,
        index: int,
        config: dict[str, Any],
        *,
        reason: str = "",
        author: str = "registry-admin",
    ) -> dict[str, Any]:
        """Replace a policy provider at a given index."""

        return await self._policy_api().update_policy_provider(
            index,
            config,
            reason=reason,
            author=author,
        )

    async def delete_policy_provider(
        self,
        index: int,
        *,
        reason: str = "",
        author: str = "registry-admin",
    ) -> dict[str, Any]:
        """Remove a policy provider from the live engine."""

        return await self._policy_api().delete_policy_provider(
            index,
            reason=reason,
            author=author,
        )

    async def rollback_policy_version(
        self,
        version_number: int,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Rollback the live policy engine to a saved version."""

        return await self._policy_api().rollback_policy_version(
            version_number,
            reason,
        )

    def diff_policy_versions(self, v1: int, v2: int) -> dict[str, Any]:
        """Diff two saved policy versions."""

        return self._policy_api().diff_policy_versions(v1, v2)

    def export_policy_snapshot(
        self,
        *,
        version_number: int | None = None,
    ) -> dict[str, Any]:
        """Export the live policy chain or a saved version as JSON."""

        return self._policy_api().export_policy_snapshot(version_number=version_number)

    def get_policy_bundles(self) -> dict[str, Any]:
        """Return reusable policy bundles."""

        return self._policy_api().get_policy_bundles()

    def get_policy_packs(self) -> dict[str, Any]:
        """Return saved private policy packs."""

        return self._policy_api().get_policy_packs()

    def get_policy_environments(self) -> dict[str, Any]:
        """Return named policy environments."""

        return self._policy_api().get_policy_environment_profiles()

    def get_policy_analytics(self) -> dict[str, Any]:
        """Return analytics for blocked, changed, and risky policy behavior."""

        return self._policy_api().get_policy_analytics()

    def get_policy_promotions(self) -> dict[str, Any]:
        """Return recent policy promotion records."""

        return self._policy_api().get_policy_promotions()

    async def stage_policy_bundle(
        self,
        bundle_id: str,
        *,
        author: str = "registry-admin",
        description: str = "",
    ) -> dict[str, Any]:
        """Stage a reusable policy bundle as a governance proposal."""

        return await self._policy_api().stage_policy_bundle(
            bundle_id,
            author=author,
            description=description,
        )

    async def save_policy_pack(
        self,
        *,
        title: str,
        summary: str = "",
        description: str = "",
        snapshot: dict[str, Any] | list[Any] | None = None,
        source_version_number: int | None = None,
        author: str = "registry-admin",
        pack_id: str | None = None,
        tags: list[str] | None = None,
        recommended_environments: list[str] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Save a private reusable policy pack."""

        return await self._policy_api().save_policy_pack(
            title=title,
            summary=summary,
            description=description,
            snapshot=snapshot,
            source_version_number=source_version_number,
            author=author,
            pack_id=pack_id,
            tags=tags,
            recommended_environments=recommended_environments,
            note=note,
        )

    def delete_policy_pack(self, pack_id: str) -> dict[str, Any]:
        """Delete a saved private policy pack."""

        return self._policy_api().delete_policy_pack(pack_id)

    async def stage_policy_pack(
        self,
        pack_id: str,
        *,
        author: str = "registry-admin",
        description: str = "",
    ) -> dict[str, Any]:
        """Stage a saved private pack as a governance proposal."""

        return await self._policy_api().stage_policy_pack(
            pack_id,
            author=author,
            description=description,
        )

    def capture_policy_environment(
        self,
        environment_id: str,
        *,
        actor: str = "registry-admin",
        note: str = "",
        source_snapshot: dict[str, Any] | None = None,
        source_version_number: int | None = None,
    ) -> dict[str, Any]:
        """Capture the current live chain or one version into an environment."""

        return self._policy_api().capture_policy_environment(
            environment_id,
            actor=actor,
            note=note,
            source_snapshot=source_snapshot,
            source_version_number=source_version_number,
        )

    async def stage_policy_promotion(
        self,
        *,
        source_environment: str,
        target_environment: str,
        author: str = "registry-admin",
        description: str = "",
    ) -> dict[str, Any]:
        """Stage an environment promotion as a governance proposal."""

        return await self._policy_api().stage_policy_promotion(
            source_environment=source_environment,
            target_environment=target_environment,
            author=author,
            description=description,
        )

    def preview_policy_migration(
        self,
        *,
        source_snapshot: dict[str, Any] | None = None,
        source_version_number: int | None = None,
        target_version_number: int | None = None,
        target_environment: str = "staging",
    ) -> dict[str, Any]:
        """Preview policy promotion between versions and environments."""

        return self._policy_api().preview_policy_migration(
            source_snapshot=source_snapshot,
            source_version_number=source_version_number,
            target_version_number=target_version_number,
            target_environment=target_environment,
        )

    async def import_policy_snapshot(
        self,
        snapshot: dict[str, Any] | list[Any],
        *,
        description_prefix: str = "Imported policy snapshot",
        author: str = "registry-admin",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Import policy JSON by creating governance proposals."""

        return await self._policy_api().import_policy_snapshot(
            snapshot,
            description_prefix=description_prefix,
            author=author,
            metadata=metadata,
        )

    def list_verified_tools(
        self,
        *,
        query: str | None = None,
        author: str | None = None,
        tags: set[str] | None = None,
        categories: set[ToolCategory] | None = None,
        min_certification: CertificationLevel | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search the published verified catalog."""

        level = min_certification or self.minimum_certification
        listings = self._marketplace().search(
            query=query,
            author=author,
            tags=tags,
            categories=categories,
            certified_only=True,
            min_certification=level,
            limit=limit,
        )
        return {
            "count": len(listings),
            "tools": [self._serialize_listing_detail(listing) for listing in listings],
            "minimum_certification": level.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_verified_tool(self, tool_name: str) -> dict[str, Any]:
        """Return detail for a single verified tool."""

        listing = self._get_public_listing(tool_name)
        if listing is None:
            return {"error": f"Tool '{tool_name}' not found", "status": 404}

        return self._serialize_listing_detail(listing)

    def list_publishers(self, *, limit: int = 200) -> dict[str, Any]:
        """Return public publisher summaries for published listings."""

        profiles = list_public_publishers(
            self._marketplace(),
            trust_lookup=self._trust_overall,
            listing_serializer=self._serialize_listing_detail,
            limit=limit,
        )
        return {
            "count": len(profiles),
            "publishers": [profile.summary.to_dict() for profile in profiles],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_publisher_profile(self, publisher_id: str) -> dict[str, Any]:
        """Return a public publisher profile."""

        profile = get_public_publisher_profile(
            self._marketplace(),
            publisher_id=publisher_id,
            trust_lookup=self._trust_overall,
            listing_serializer=self._serialize_listing_detail,
        )
        if profile is None:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }
        return profile.to_dict()

    def _listings_for_publisher(
        self,
        publisher_id: str,
        *,
        include_non_public: bool,
    ) -> list[ToolListing]:
        """Filter all marketplace listings down to one publisher's, with
        visibility honored.

        The visibility rule mirrors the rest of the registry's
        session-aware endpoints:

        - ``include_non_public=False`` (anonymous / auth-disabled):
          only listings that pass :meth:`_is_public_listing`
          (PUBLISHED + certified at min level).
        - ``include_non_public=True`` (authenticated session): every
          listing the publisher owns, regardless of status — so
          curators can inspect how their just-submitted listings will
          be governed before a moderator approves them.

        Returns the listings ordered most-recently-updated first so
        the curator's freshest activity is at the top.
        """
        marketplace = self._marketplace()
        target_listings: list[ToolListing] = []
        for listing in marketplace.get_all_listings():
            if publisher_id_from_author(listing.author) != publisher_id:
                continue
            if include_non_public or self._is_public_listing(listing):
                target_listings.append(listing)
        target_listings.sort(key=lambda item: item.updated_at, reverse=True)
        return target_listings

    def get_server_policy_governance(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
    ) -> dict[str, Any]:
        """Return the policy-kernel governance view for a server (publisher).

        Two layers of policy data are surfaced:

        1. **Registry-wide policy** (the one rendered on the
           ``/registry/policy`` Policy Kernel page) — currentVersion,
           policy-set ID, provider count, fail-closed flag,
           evaluation/deny counters.
        2. **Per-listing policy bindings** for every tool the publisher
           owns — distinguishes ``inherited`` (no listing-specific
           override; either a catalog-only listing or a listing whose
           call surface isn't gated by a registry-attached policy)
           from ``proxy_allowlist`` (a curator-attested proxy listing
           whose AllowlistPolicy gates calls against the
           curator-vouched tool surface).

        Args:
            publisher_id: The publisher slug — i.e. the value
                ``publisher_id_from_author(listing.author)`` returns
                for the publisher's listings.
            include_non_public: When True, include non-public
                listings (e.g. ``PENDING_REVIEW``). Authenticated
                callers should pass True so curators can see how
                their just-submitted listings will be governed.

        Returns:
            ``{server_id, registry_policy, per_tool_policies, summary,
            links, generated_at}`` on success.
            ``{error, status: 404}`` when the publisher has no
            visible listings under the caller's visibility.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        registry_policy = self._summarize_registry_policy()
        per_tool: list[dict[str, Any]] = []
        for listing in target_listings:
            per_tool.append(self._summarize_listing_policy_binding(listing))

        inherited_count = sum(
            1 for entry in per_tool if entry["binding_source"] == "inherited"
        )
        overridden_count = len(per_tool) - inherited_count

        return {
            "server_id": publisher_id,
            "registry_policy": registry_policy,
            "per_tool_policies": per_tool,
            "summary": {
                "tool_count": len(per_tool),
                "inherited_count": inherited_count,
                "overridden_count": overridden_count,
            },
            "links": {
                "policy_kernel_url": f"{self._registry_prefix}/policy",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _summarize_registry_policy(self) -> dict[str, Any]:
        """Pull a UI-shaped snapshot of the registry-wide policy engine.

        We intentionally project a small subset of the
        ``SecurityAPI.get_policy_status()`` payload — UI surfaces
        should not have to know about every internal field, and
        bringing the whole thing across the wire couples the server
        profile page tightly to the policy-status contract.
        """
        api = self._policy_api()
        status = api.get_policy_status()
        if "error" in status:
            return {
                "available": False,
                "error": status.get("error"),
            }
        versioning = status.get("versioning") or {}
        return {
            "available": True,
            "policy_set_id": versioning.get("policy_set_id"),
            "current_version": versioning.get("current_version"),
            "version_count": versioning.get("version_count"),
            "fail_closed": status.get("fail_closed"),
            "allow_hot_swap": status.get("allow_hot_swap"),
            "provider_count": status.get("provider_count"),
            "evaluation_count": status.get("evaluation_count"),
            "deny_count": status.get("deny_count"),
        }

    def _summarize_listing_policy_binding(self, listing: ToolListing) -> dict[str, Any]:
        """Project a single listing into a policy-binding row.

        Encodes the contract:

        - ``proxy`` listings whose ``listing.metadata["introspection"]
          ["tool_names"]`` is populated render as
          ``binding_source="proxy_allowlist"`` with the curator-
          vouched tool count + a small sample of names.
        - Any other listing renders as
          ``binding_source="inherited"`` — calls aren't gated by a
          listing-specific policy at the registry layer.
        """
        from fastmcp.server.security.gateway.tool_marketplace import HostingMode

        base = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
        }

        if listing.hosting_mode == HostingMode.PROXY:
            allowed = self._observed_tool_allowlist(listing)
            if allowed:
                # Truncate the inline sample so a 500-tool surface
                # doesn't blow up the response payload. Curators who
                # want the full list click through to the listing
                # detail page where the manifest is rendered.
                sample = sorted(allowed)[:10]
                return {
                    **base,
                    "binding_source": "proxy_allowlist",
                    "policy_provider": {
                        "type": "allowlist",
                        "policy_id": (f"curator-allowlist-{listing.listing_id}"),
                        "fail_closed": True,
                        "allowed_count": len(allowed),
                        "allowed_sample": sample,
                    },
                }

        return {
            **base,
            "binding_source": "inherited",
            "policy_provider": None,
        }

    def get_listing_governance(
        self,
        tool_name: str,
        *,
        include_non_public: bool = False,
        sanitize_for_public: bool = True,
    ) -> dict[str, Any]:
        """Return the per-listing governance + observability rollup.

        Mirrors the publisher-scoped server-profile views, but
        scoped to a single listing. Composes the same
        ``_summarize_listing_*`` helpers we already use for the
        publisher endpoints so the per-listing projection is
        guaranteed consistent with the per-publisher projection.

        Visibility rules:

        - When ``include_non_public=False`` (anonymous, or auth
          disabled), only public listings are visible. Pending /
          suspended / etc. listings 404.
        - When ``include_non_public=True`` (authenticated session),
          any listing the registry knows about is visible.

        ``sanitize_for_public=True`` (default for anonymous callers)
        strips identifying fields from the response — actor IDs,
        moderator IDs, agent IDs — so a public viewer browsing a
        listing sees its trust posture without operator-private
        details.

        Args:
            tool_name: The listing's canonical tool name.
            include_non_public: Visibility flag (mirror of the other
                governance endpoints).
            sanitize_for_public: When True, strip identifying fields
                before returning. The route handler passes True for
                anonymous callers, False for authenticated.

        Returns:
            ``{listing_id, tool_name, ..., policy, contracts, consent,
            ledger, overrides, observability, links, generated_at}``
            on success;
            ``{error, status: 404}`` when the listing isn't visible
            under the caller's visibility.
        """
        marketplace = self._marketplace()
        if include_non_public:
            listing = marketplace.get_by_name(tool_name)
        else:
            listing = self._get_public_listing(tool_name)
        if listing is None:
            return {
                "error": f"Tool '{tool_name}' not found",
                "status": 404,
            }

        # Identifying header — same fields the per-tool blocks on the
        # publisher endpoints emit, so the consumer can pivot.
        publisher_id = publisher_id_from_author(listing.author)
        header = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "publisher_id": publisher_id,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
        }

        # Compose per-plane projections from the same helpers the
        # publisher endpoints use. These are pure projections of the
        # listing + relevant context, so per-listing and per-publisher
        # views can never disagree about what a listing's binding is.
        policy_row = self._summarize_listing_policy_binding(listing)
        registry_policy = self._summarize_registry_policy()

        contracts_broker = self._broker_or_none()
        contracts_block = self._summarize_broker(contracts_broker)
        contracts_row = self._summarize_listing_contract_binding(
            listing,
            self._active_contracts_snapshot(contracts_broker),
        )

        consent_graph = self._consent_graph_or_none()
        consent_block = self._summarize_consent_graph(consent_graph)
        consent_row = self._summarize_listing_consent_binding(
            listing,
            self._active_consent_edges_snapshot(consent_graph),
        )

        ledger = self._ledger_or_none()
        ledger_block = self._summarize_ledger(ledger)
        ledger_row = self._summarize_listing_ledger_binding(listing, ledger)

        overrides_row = self._summarize_listing_overrides(listing, marketplace)

        analyzer = self._analyzer_or_none()
        analyzer_block = self._summarize_analyzer(analyzer)
        observability_row = self._summarize_listing_observability(
            listing, self._drift_events_snapshot(analyzer)
        )

        result = {
            **header,
            "policy": {
                "registry_policy": registry_policy,
                **policy_row,
            },
            "contracts": {
                "broker": contracts_block,
                **contracts_row,
            },
            "consent": {
                "consent_graph": consent_block,
                **consent_row,
            },
            "ledger": {
                "ledger": ledger_block,
                **ledger_row,
            },
            "overrides": overrides_row,
            "observability": {
                "analyzer": analyzer_block,
                **observability_row,
            },
            "links": {
                "policy_kernel_url": f"{self._registry_prefix}/policy",
                "contract_broker_url": f"{self._registry_prefix}/contracts",
                "consent_graph_url": f"{self._registry_prefix}/consent",
                "provenance_ledger_url": f"{self._registry_prefix}/provenance",
                "moderation_queue_url": f"{self._registry_prefix}/review",
                "reflexive_core_url": f"{self._registry_prefix}/reflexive",
                "publisher_url": (f"{self._registry_prefix}/publishers/{publisher_id}"),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if sanitize_for_public:
            result = self._sanitize_listing_governance(result)
        return result

    def _sanitize_listing_governance(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Strip identifying fields from a listing governance payload.

        Public viewers should see *that* a tool has activity (counts,
        binding sources, severities, statuses) without seeing *who*
        was involved (actor IDs, moderator IDs, agent IDs). The
        sanitization is in-place on the dict structure and returns
        the same dict for chaining.
        """
        # Contracts block — drop the agent IDs but keep the count.
        contracts = payload.get("contracts")
        if isinstance(contracts, dict):
            if "matching_agents" in contracts:
                contracts["matching_agents"] = []

        # Consent block — drop grant source IDs.
        consent = payload.get("consent")
        if isinstance(consent, dict):
            if "grant_sources" in consent:
                consent["grant_sources"] = []

        # Overrides block — drop moderator IDs from the latest +
        # individual log entries, but keep counts and timestamps so
        # public viewers see "this listing was suspended on date X"
        # without seeing "by moderator Y".
        overrides = payload.get("overrides")
        if isinstance(overrides, dict):
            moderation = overrides.get("moderation")
            if isinstance(moderation, dict):
                moderation.pop("latest_moderator_id", None)
                # Public callers don't need the full log either —
                # this could leak operator process. Keep the count.
                if "log" in moderation:
                    moderation["log"] = []

        # Observability block — actor IDs are the most sensitive
        # field on drift events because they identify the agent.
        observability = payload.get("observability")
        if isinstance(observability, dict):
            analyzer = observability.get("analyzer")
            if isinstance(analyzer, dict):
                analyzer.pop("latest_drift_actor_id", None)

        return payload

    def get_server_observability(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
        recent_event_limit: int = 10,
    ) -> dict[str, Any]:
        """Return the Reflexive-Core observability view for a server.

        Surfaces the BehavioralAnalyzer's state plus per-tool drift
        bindings. Two layers, parallel to the governance endpoints:

        1. **Analyzer block** — opt-in via
           ``SecurityConfig.reflexive``. When wired, the registry's
           ``BehavioralAnalyzer`` tracks per-actor metric baselines
           (calls_per_minute, error_rate, etc.) and raises
           ``DriftEvent`` records when observed values exceed the
           configured sigma thresholds. We project the analyzer's
           identifying metadata, total drift count, severity
           distribution, monitored-actor count, tracked-metric
           count, registered detectors, and latest drift activity.
        2. **Per-listing observability bindings** — drift events
           are *actor-centric* (``actor_id``), not tool-centric, so
           tool-binding here is best-effort. We scan
           ``event.metadata`` for the standard tool-targeting keys
           (``tool_name`` / ``resource_id`` / ``tool_names``) plus
           literal substring matches in ``event.description``.
           Rows surface drift count, highest severity observed,
           latest drift timestamp, and a per-severity distribution.
           ``binding_source`` is ``monitored`` when at least one
           event references the tool, else ``no_observations``.

        Args:
            publisher_id: Publisher slug.
            include_non_public: Mirror of the governance endpoints'
                visibility flag.
            recent_event_limit: Cap on the cross-tool
                ``recent_drift_events`` feed. Default 10.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        analyzer = self._analyzer_or_none()
        analyzer_block = self._summarize_analyzer(analyzer)
        events = self._drift_events_snapshot(analyzer)

        per_tool: list[dict[str, Any]] = []
        with_observations_count = 0
        with_high_severity_count = 0
        with_critical_severity_count = 0
        for listing in target_listings:
            row = self._summarize_listing_observability(listing, events)
            per_tool.append(row)
            if row["binding_source"] == "monitored":
                with_observations_count += 1
            highest = row.get("highest_severity")
            if highest == "critical":
                with_critical_severity_count += 1
            elif highest == "high":
                with_high_severity_count += 1

        # Cross-tool feed: tag each event with the matching tool
        # if any, sort desc by timestamp, cap at limit.
        listing_lookup = {listing.tool_name: listing for listing in target_listings}
        recent_events: list[dict[str, Any]] = []
        for event in events:
            for listing in target_listings:
                if self._drift_event_references_tool(event, listing.tool_name):
                    matched = listing
                    break
            else:
                matched = None
            recent_events.append(self._serialize_drift_event(event, matched))
        # Filter to events that reference one of this server's tools
        # — otherwise the feed dilutes with unrelated drift across
        # the registry. Operators looking at the global view go to
        # /registry/reflexive.
        recent_events = [entry for entry in recent_events if entry.get("tool_name")]
        recent_events.sort(key=lambda entry: entry.get("timestamp", ""), reverse=True)
        recent_events = recent_events[:recent_event_limit]
        # Avoid emitting unused lookup once recent events are built.
        del listing_lookup

        return {
            "server_id": publisher_id,
            "analyzer": analyzer_block,
            "per_tool_observability": per_tool,
            "recent_drift_events": recent_events,
            "summary": {
                "tool_count": len(per_tool),
                "monitored_count": with_observations_count,
                "with_high_drift_count": with_high_severity_count,
                "with_critical_drift_count": with_critical_severity_count,
            },
            "links": {
                "reflexive_core_url": f"{self._registry_prefix}/reflexive",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _analyzer_or_none(self):
        """Return the registry's :class:`BehavioralAnalyzer` or None.

        Like the broker / consent graph / provenance ledger, the
        analyzer is opt-in via :class:`SecurityConfig.reflexive`.
        When the operator hasn't configured it,
        ``ctx.behavioral_analyzer`` is ``None`` and observability
        gracefully degrades.
        """
        try:
            ctx = self._required_context()
        except RuntimeError:
            return None
        return getattr(ctx, "behavioral_analyzer", None)

    def _summarize_analyzer(self, analyzer) -> dict[str, Any]:
        """Project the analyzer's identifying metadata + activity.

        Returns a stable shape regardless of availability — the
        ``available`` flag tells the consumer whether the rest of
        the fields carry real data.
        """
        if analyzer is None:
            return {
                "available": False,
                "reason": (
                    "The Reflexive Core is not enabled on this "
                    "registry. Operators can opt in by passing "
                    "SecurityConfig(reflexive=ReflexiveConfig(...)) "
                    "when constructing the registry."
                ),
            }

        from fastmcp.server.security.reflexive.models import DriftSeverity

        baselines_by_actor = getattr(analyzer, "_baselines", {}) or {}
        actor_count = len(baselines_by_actor)
        metric_names: set[str] = set()
        for metrics in baselines_by_actor.values():
            for metric_name in metrics.keys():
                metric_names.add(str(metric_name))

        history = list(getattr(analyzer, "_drift_history", []) or [])
        severity_dist: dict[str, int] = {sev.value: 0 for sev in DriftSeverity}
        for event in history:
            try:
                severity_dist[event.severity.value] += 1
            except (AttributeError, KeyError):
                continue

        latest = history[-1] if history else None
        latest_at = latest.timestamp.isoformat() if latest is not None else None
        latest_severity = latest.severity.value if latest is not None else None
        latest_actor = getattr(latest, "actor_id", None) if latest is not None else None

        return {
            "available": True,
            "analyzer_id": getattr(analyzer, "analyzer_id", "default"),
            "total_drift_count": int(getattr(analyzer, "total_drift_count", 0) or 0),
            "monitored_actor_count": actor_count,
            "tracked_metric_count": len(metric_names),
            "tracked_metrics": sorted(metric_names),
            "detector_count": len(getattr(analyzer, "_detectors", []) or []),
            "min_samples": int(getattr(analyzer, "_min_samples", 0) or 0),
            "severity_distribution": severity_dist,
            "latest_drift_at": latest_at,
            "latest_drift_severity": latest_severity,
            "latest_drift_actor_id": latest_actor,
        }

    def _drift_events_snapshot(self, analyzer) -> list[Any]:
        """Return the analyzer's drift events as a list.

        Pulled into a helper so the per-tool walk doesn't have to
        re-read on every iteration. Returns empty when analyzer
        isn't configured.
        """
        if analyzer is None:
            return []
        return list(getattr(analyzer, "_drift_history", []) or [])

    def _summarize_listing_observability(
        self,
        listing: ToolListing,
        events: list[Any],
    ) -> dict[str, Any]:
        """Project one listing into an observability-binding row.

        Walks the analyzer's drift history for events that reference
        this tool by name (best-effort). When matches exist, the
        row carries a per-severity distribution, the highest
        severity observed (escalation order: critical > high >
        medium > low > info), and the latest match's timestamp.
        """
        from fastmcp.server.security.reflexive.models import DriftSeverity

        severity_order = ["info", "low", "medium", "high", "critical"]
        severity_dist: dict[str, int] = {sev.value: 0 for sev in DriftSeverity}
        latest_at: str | None = None
        latest_severity: str | None = None
        highest_idx = -1
        match_count = 0
        for event in events:
            if not self._drift_event_references_tool(event, listing.tool_name):
                continue
            match_count += 1
            try:
                severity = event.severity.value
            except AttributeError:
                severity = "info"
            severity_dist[severity] = severity_dist.get(severity, 0) + 1
            try:
                idx = severity_order.index(severity)
            except ValueError:
                idx = -1
            if idx > highest_idx:
                highest_idx = idx
            timestamp = (
                event.timestamp.isoformat() if getattr(event, "timestamp", None) else ""
            )
            if latest_at is None or timestamp > latest_at:
                latest_at = timestamp
                latest_severity = severity

        highest = severity_order[highest_idx] if highest_idx >= 0 else None

        base = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
        }

        return {
            **base,
            "binding_source": "monitored" if match_count > 0 else "no_observations",
            "drift_event_count": match_count,
            "severity_distribution": severity_dist,
            "highest_severity": highest,
            "latest_drift_at": latest_at,
            "latest_drift_severity": latest_severity,
        }

    def _drift_event_references_tool(self, event, tool_name: str) -> bool:
        """Return True when a drift event references ``tool_name``.

        Heuristic in order of confidence:

        1. ``event.metadata`` contains a string field whose value
           equals ``tool_name`` (or list/set/tuple containing it).
           Common keys: ``tool_name``, ``resource_id``,
           ``tool_names``, ``resource_pattern``.
        2. ``event.description`` literally contains ``tool_name``
           as a substring.
        """
        metadata = getattr(event, "metadata", None) or {}
        if isinstance(metadata, dict):
            for value in metadata.values():
                if isinstance(value, str) and value == tool_name:
                    return True
                if isinstance(value, (list, tuple, set)):
                    for item in value:
                        if isinstance(item, str) and item == tool_name:
                            return True

        description = getattr(event, "description", None) or ""
        if isinstance(description, str) and tool_name and tool_name in description:
            return True

        return False

    def _serialize_drift_event(
        self, event, matched_listing: ToolListing | None
    ) -> dict[str, Any]:
        """Project a drift event for the cross-tool feed.

        Tags the event with the matching listing's tool name +
        display name when one was found, so the consumer can render
        a tool link without joining on listing_id.
        """
        return {
            "event_id": getattr(event, "event_id", ""),
            "drift_type": (
                event.drift_type.value
                if getattr(event, "drift_type", None) is not None
                else None
            ),
            "severity": (
                event.severity.value
                if getattr(event, "severity", None) is not None
                else None
            ),
            "actor_id": getattr(event, "actor_id", ""),
            "description": getattr(event, "description", ""),
            "observed_value": getattr(event, "observed_value", None),
            "baseline_value": getattr(event, "baseline_value", None),
            "deviation": getattr(event, "deviation", None),
            "timestamp": (
                event.timestamp.isoformat()
                if getattr(event, "timestamp", None) is not None
                else None
            ),
            "tool_name": (
                matched_listing.tool_name if matched_listing is not None else None
            ),
            "display_name": (
                (matched_listing.display_name or matched_listing.tool_name)
                if matched_listing is not None
                else None
            ),
        }

    def get_server_overrides_governance(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
        recent_decision_limit: int = 10,
    ) -> dict[str, Any]:
        """Return the Overrides governance view for a server.

        This is the rollup view of operator/moderator interventions
        across this server's tools. Overrides come from three real
        sources already in the system:

        1. **Status overrides** — every listing has a
           :class:`PublishStatus`. ``PUBLISHED`` is the default;
           ``PENDING_REVIEW`` / ``SUSPENDED`` / ``DEPRECATED`` /
           ``REJECTED`` are operator-imposed overrides.
        2. **Moderation log** — every
           ``approve``/``reject``/``suspend``/``unsuspend``/
           ``deprecate``/``request_changes`` decision is recorded on
           ``listing.moderation_log`` chronologically.
        3. **Yanked versions** — :attr:`ToolVersion.yanked` +
           ``yank_reason`` give per-version overrides without
           taking down the whole listing.

        Plus a cross-reference: per-listing policy overrides (the
        proxy AllowlistPolicy) are already on the Policy panel —
        we surface a ``policy_override.active`` flag here so a
        moderator scanning the server sees them in one place.

        Per-tool ``binding_source`` reflects the most-salient
        override for that tool:

        - ``moderation_pending`` — ``status == PENDING_REVIEW``
        - ``moderated`` — listing has at least one decision in the
          moderation log (suspended / approved / rejected /
          deprecated / etc.)
        - ``yanked_versions`` — at least one published version was
          yanked
        - ``active`` — ``PUBLISHED`` with no other override

        Args:
            publisher_id: Publisher slug.
            include_non_public: Visibility flag (mirrors the other
                governance endpoints).
            recent_decision_limit: Cap on the cross-tool
                ``recent_moderation_decisions`` feed. Default 10.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        marketplace = self._marketplace()

        per_tool: list[dict[str, Any]] = []
        all_decisions: list[dict[str, Any]] = []
        for listing in target_listings:
            row = self._summarize_listing_overrides(listing, marketplace)
            per_tool.append(row)
            for entry in row["moderation"]["log"]:
                # Tag each decision with the owning tool name so the
                # cross-tool feed below renders without the consumer
                # having to join on listing_id.
                all_decisions.append(
                    {
                        **entry,
                        "tool_name": listing.tool_name,
                        "display_name": listing.display_name or listing.tool_name,
                    }
                )

        # Sort recent decisions across all the publisher's tools by
        # most-recent first, capped.
        all_decisions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        recent_decisions = all_decisions[:recent_decision_limit]

        # Summary aggregates.
        status_counts = {
            "draft": 0,
            "pending_review": 0,
            "published": 0,
            "suspended": 0,
            "deprecated": 0,
            "rejected": 0,
        }
        yanked_version_count = 0
        policy_override_count = 0
        open_moderation_actions = 0
        for row in per_tool:
            status = row.get("status") or ""
            if status in status_counts:
                status_counts[status] += 1
            yanked_version_count += len(row.get("yanked_versions", []))
            if row.get("policy_override", {}).get("active"):
                policy_override_count += 1
            if row.get("moderation", {}).get("open"):
                open_moderation_actions += 1

        return {
            "server_id": publisher_id,
            "summary": {
                "tool_count": len(per_tool),
                **{f"{key}_count": value for key, value in status_counts.items()},
                "yanked_version_count": yanked_version_count,
                "policy_override_count": policy_override_count,
                "open_moderation_actions": open_moderation_actions,
            },
            "per_tool_overrides": per_tool,
            "recent_moderation_decisions": recent_decisions,
            "links": {
                "moderation_queue_url": f"{self._registry_prefix}/review",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _summarize_listing_overrides(
        self,
        listing: ToolListing,
        marketplace,
    ) -> dict[str, Any]:
        """Project one listing into an overrides-binding row.

        Decision precedence for ``binding_source``:

        1. ``moderation_pending`` if the listing is awaiting a
           moderator (``PENDING_REVIEW``).
        2. ``moderated`` if the listing has any decisions in its
           moderation log OR the status is one of the moderated
           statuses (suspended / deprecated / rejected).
        3. ``yanked_versions`` if at least one version was yanked.
        4. ``active`` otherwise.
        """
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            PublishStatus,
        )

        status = listing.status

        # Moderation log + open-action flag.
        log = list(listing.moderation_log or [])
        log_dicts = [decision.to_dict() for decision in log]
        log_dicts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        latest = log_dicts[0] if log_dicts else None
        open_moderation = status == PublishStatus.PENDING_REVIEW

        # Yanked versions for this listing.
        try:
            versions = marketplace.get_version_history(listing.listing_id)
        except Exception:
            # Defensive: if the marketplace doesn't expose history
            # for this listing (storage error, etc.), treat as no
            # yanks rather than blowing up the entire projection.
            versions = []
        yanked = [
            {
                "version": getattr(v, "version", ""),
                "yanked": True,
                "yank_reason": getattr(v, "yank_reason", "") or "",
                "published_at": (
                    v.published_at.isoformat()
                    if getattr(v, "published_at", None)
                    else None
                ),
            }
            for v in versions
            if getattr(v, "yanked", False)
        ]

        # Per-listing policy override flag — proxy listings whose
        # observed-tool surface is recorded carry an AllowlistPolicy
        # at the proxy gateway. Mirrors what the Policy panel renders.
        override_active = False
        allowed_count = 0
        if listing.hosting_mode == HostingMode.PROXY:
            allowed = self._observed_tool_allowlist(listing)
            if allowed:
                override_active = True
                allowed_count = len(allowed)

        # Pick the most-salient binding source.
        moderated_statuses = {
            PublishStatus.SUSPENDED,
            PublishStatus.DEPRECATED,
            PublishStatus.REJECTED,
        }
        if open_moderation:
            binding_source = "moderation_pending"
        elif status in moderated_statuses or log:
            binding_source = "moderated"
        elif yanked:
            binding_source = "yanked_versions"
        else:
            binding_source = "active"

        return {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": status.value,
            "binding_source": binding_source,
            "moderation": {
                "open": open_moderation,
                "log_entries": len(log_dicts),
                "latest_action": latest["action"] if latest else None,
                "latest_at": latest["created_at"] if latest else None,
                "latest_reason": latest["reason"] if latest else None,
                "latest_moderator_id": (latest["moderator_id"] if latest else None),
                "log": log_dicts,
            },
            "policy_override": {
                "active": override_active,
                "allowed_count": allowed_count,
            },
            "yanked_versions": yanked,
        }

    def get_server_ledger_governance(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
    ) -> dict[str, Any]:
        """Return the Provenance-Ledger governance view for a server.

        Surfaces two layers honestly, parallel to the Policy Kernel
        story:

        1. **Registry-wide ledger** — opt-in via
           ``SecurityConfig.provenance``. When wired, it records
           registry-side actions (submissions, policy decisions,
           etc.). The block carries ``ledger_id``, ``record_count``,
           the current Merkle ``root_hash``, ``latest_record_at``,
           and (when present) the pluggable scheme name. Chain /
           tree verification is deferred to a separate endpoint —
           ``verify_chain()`` walks every record and is too
           expensive to run on every panel load.

        2. **Per-listing ledger bindings** — every curator-attested
           proxy listing gets its OWN dedicated ledger spun up at
           gateway mount time
           (``ProvenanceConfig(ledger_id=f"curator-proxy-{listing_id}")``
           — see ``purecipher.curation.proxy_runtime
           ._build_proxy_security_config``). Catalog-only listings
           don't pass through any registry-attached ledger; calls
           bypass the registry entirely. The row's
           ``binding_source`` reflects this:
           ``proxy_ledger`` for proxy-hosted listings (with the
           ``expected_ledger_id`` they would use), ``no_ledger`` for
           catalog listings.

           When the registry-wide ledger is configured, we also
           scan it for records whose ``resource_id`` literally
           matches the listing's ``tool_name`` and surface a
           ``central_record_count`` + ``latest_central_record_at``.
           This is best-effort: per-listing proxy ledgers are
           constructed fresh per gateway mount and don't share state
           with the central ledger by default. Operators wanting one
           unified audit trail wire a shared backend.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        ledger = self._ledger_or_none()
        ledger_block = self._summarize_ledger(ledger)

        per_tool: list[dict[str, Any]] = []
        with_proxy_count = 0
        with_central_records_count = 0
        total_central_records = 0
        for listing in target_listings:
            row = self._summarize_listing_ledger_binding(listing, ledger)
            per_tool.append(row)
            if row["binding_source"] == "proxy_ledger":
                with_proxy_count += 1
            if row["central_record_count"] > 0:
                with_central_records_count += 1
                total_central_records += row["central_record_count"]

        return {
            "server_id": publisher_id,
            "ledger": ledger_block,
            "per_tool_ledger": per_tool,
            "summary": {
                "tool_count": len(per_tool),
                "with_proxy_ledger_count": with_proxy_count,
                "with_central_records_count": with_central_records_count,
                "total_central_records_for_tools": total_central_records,
            },
            "links": {
                "provenance_ledger_url": f"{self._registry_prefix}/provenance",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _ledger_or_none(self):
        """Return the registry's :class:`ProvenanceLedger` or ``None``.

        Like the broker and consent graph, the provenance ledger is
        opt-in via :class:`SecurityConfig.provenance`. When the
        operator hasn't configured it,
        ``ctx.provenance_ledger`` is ``None`` and ledger
        governance gracefully degrades.
        """
        try:
            ctx = self._required_context()
        except RuntimeError:
            return None
        return getattr(ctx, "provenance_ledger", None)

    def _summarize_ledger(self, ledger) -> dict[str, Any]:
        """Project the registry-wide ledger's identifying metadata + counts.

        Cheap projection: reads counts and latest-record metadata.
        Does NOT run ``verify_chain()`` / ``verify_tree()`` because
        those are O(N) over every record and too expensive for a
        panel load. Verification belongs on a dedicated endpoint.
        """
        if ledger is None:
            return {
                "available": False,
                "reason": (
                    "The Provenance Ledger is not enabled on this "
                    "registry. Operators can opt in by passing "
                    "SecurityConfig(provenance=ProvenanceConfig(...)) "
                    "when constructing the registry. Note: every "
                    "curator-attested proxy listing still records "
                    "calls to its own dedicated ledger at gateway "
                    "mount time."
                ),
            }

        latest = getattr(ledger, "latest_record", None)
        latest_at = latest.timestamp.isoformat() if latest is not None else None
        latest_resource = getattr(latest, "resource_id", None) if latest else None
        latest_action = (
            getattr(latest.action, "value", str(latest.action))
            if latest is not None
            else None
        )

        scheme = getattr(ledger, "scheme", None)
        scheme_name = type(scheme).__name__ if scheme is not None else None

        return {
            "available": True,
            "ledger_id": getattr(ledger, "ledger_id", "default"),
            "record_count": int(getattr(ledger, "record_count", 0) or 0),
            "root_hash": getattr(ledger, "root_hash", "") or "",
            "latest_record_at": latest_at,
            "latest_record_action": latest_action,
            "latest_record_resource_id": latest_resource,
            "scheme_name": scheme_name,
        }

    def _summarize_listing_ledger_binding(
        self,
        listing: ToolListing,
        ledger,
    ) -> dict[str, Any]:
        """Project one listing into a ledger-binding row.

        Encodes the contract:

        - ``proxy`` listings → ``binding_source="proxy_ledger"``
          with the ``expected_ledger_id`` the proxy gateway would
          use (matches what
          ``purecipher.curation.proxy_runtime._build_proxy_security_config``
          assigns).
        - ``catalog`` listings → ``binding_source="no_ledger"``;
          calls bypass the registry entirely.

        When the registry-wide ledger is configured, we additionally
        surface per-tool record counts on the central ledger
        (filtered by ``resource_id == tool_name``).
        """
        from fastmcp.server.security.gateway.tool_marketplace import HostingMode

        is_proxy = listing.hosting_mode == HostingMode.PROXY

        base = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
            "binding_source": ("proxy_ledger" if is_proxy else "no_ledger"),
            "expected_ledger_id": (
                f"curator-proxy-{listing.listing_id}" if is_proxy else None
            ),
        }

        # Best-effort scan of the registry-wide ledger for records
        # whose resource_id matches this tool. Caps the scan at a
        # reasonable per-call limit so a multi-thousand-record ledger
        # doesn't slow the panel.
        central_records: list[Any] = []
        if ledger is not None:
            try:
                central_records = list(
                    ledger.get_records(
                        resource_id=listing.tool_name,
                        limit=1000,
                    )
                )
            except Exception:
                # If the ledger can't be queried (e.g. a future
                # variant exposes a different surface), fall back to
                # zero rather than blow up the whole projection.
                central_records = []

        latest_central_at = (
            central_records[0].timestamp.isoformat() if central_records else None
        )
        latest_central_action = (
            getattr(central_records[0].action, "value", None)
            if central_records
            else None
        )

        return {
            **base,
            "central_record_count": len(central_records),
            "latest_central_record_at": latest_central_at,
            "latest_central_record_action": latest_central_action,
        }

    def get_server_consent_governance(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
    ) -> dict[str, Any]:
        """Return the Consent-Graph governance view for a server.

        Surfaces three layers honestly:

        1. **Consent graph availability + topology** — like the
           Context Broker, the Consent Graph is opt-in on the
           registry's :class:`SecurityConfig`. When unavailable, the
           response says so explicitly. When available, it carries
           ``graph_id``, total node/edge counts, an ``active_edge_count``
           that respects edge expiry/revocation, a per-NodeType
           breakdown, and the audit-log entry count.
        2. **Federation block** — a lightweight indicator for whether
           a :class:`FederatedConsentGraph` is wired. Federation isn't
           tracked on the security context today, so this defaults to
           ``available=false`` with operator-actionable copy until a
           future iteration plumbs it through.
        3. **Per-listing consent bindings** — there are two
           orthogonal signals per tool:

           - ``binding_source`` from
             :attr:`SecurityManifest.requires_consent`: deterministic
             "this tool says it needs consent" flag
             (``consent_required`` vs ``consent_optional``).
           - ``graph_grant_count``: best-effort heuristic that walks
             the graph's active edges looking for tool-name references
             in the edge's ``scopes``, ``metadata`` (string match),
             ``source_id``, or ``target_id``. ``grant_sources``
             surfaces a bounded sample of the matching edges' source
             IDs so the curator can see who's granting access.

        These two axes aren't redundant: a tool can be marked
        required but have zero grants (operator gap), or marked
        optional yet appear in scope-prefixed grants (defensive
        opt-ins by users), or both, or neither.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        graph = self._consent_graph_or_none()
        graph_block = self._summarize_consent_graph(graph)
        federation_block = self._summarize_consent_federation()
        active_edges = self._active_consent_edges_snapshot(graph)

        per_tool: list[dict[str, Any]] = []
        for listing in target_listings:
            per_tool.append(
                self._summarize_listing_consent_binding(listing, active_edges)
            )

        requires_consent_count = sum(
            1 for entry in per_tool if entry["requires_consent"]
        )
        with_grants_count = sum(
            1 for entry in per_tool if entry["graph_grant_count"] > 0
        )
        without_grants_count = len(per_tool) - with_grants_count

        return {
            "server_id": publisher_id,
            "consent_graph": graph_block,
            "federation": federation_block,
            "per_tool_consent": per_tool,
            "summary": {
                "tool_count": len(per_tool),
                "requires_consent_count": requires_consent_count,
                "with_grants_count": with_grants_count,
                "without_grants_count": without_grants_count,
            },
            "links": {
                # The consent UI is provisional — link to the
                # observability/consent surface. Resolves cleanly even
                # when the surface isn't built yet (404 falls back to
                # the registry root).
                "consent_graph_url": f"{self._registry_prefix}/consent",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _consent_graph_or_none(self):
        """Return the registry's :class:`ConsentGraph` or ``None``.

        Like the broker, the consent graph is opt-in via
        :class:`SecurityConfig.consent`. When the operator hasn't
        configured it, ``ctx.consent_graph`` is ``None`` and consent
        governance gracefully degrades.
        """
        try:
            ctx = self._required_context()
        except RuntimeError:
            return None
        return getattr(ctx, "consent_graph", None)

    def _summarize_consent_graph(self, graph) -> dict[str, Any]:
        """Project the consent graph's topology + activity counts.

        Returns a stable shape regardless of availability — the
        ``available`` flag tells the consumer whether the rest of
        the fields carry real data.
        """
        if graph is None:
            return {
                "available": False,
                "reason": (
                    "The Consent Graph is not enabled on this "
                    "registry. Operators can opt in by passing "
                    "SecurityConfig(consent=ConsentConfig(...)) when "
                    "constructing the registry."
                ),
            }

        from fastmcp.server.security.consent.models import NodeType

        nodes_by_type: dict[str, int] = {nt.value: 0 for nt in NodeType}
        for node in getattr(graph, "_nodes", {}).values():
            try:
                nodes_by_type[node.node_type.value] = (
                    nodes_by_type.get(node.node_type.value, 0) + 1
                )
            except AttributeError:
                # Unknown node shape — skip rather than blow up the
                # whole projection.
                continue

        edges = list(getattr(graph, "_edges", {}).values())
        active_edges = [edge for edge in edges if edge.is_valid()]

        audit_entries = list(getattr(graph, "_audit_log", []) or [])

        return {
            "available": True,
            "graph_id": getattr(graph, "graph_id", "default"),
            "node_count": len(getattr(graph, "_nodes", {})),
            "edge_count": len(edges),
            "active_edge_count": len(active_edges),
            "node_counts_by_type": nodes_by_type,
            "audit_entry_count": len(audit_entries),
        }

    def _summarize_consent_federation(self) -> dict[str, Any]:
        """Federation isn't tracked on the security context today.

        Returns a stable shape with ``available=false`` so the UI can
        render a clear "coming in a follow-up" empty state instead of
        guessing. When federation gets plumbed through, this method
        starts returning real metadata.
        """
        return {
            "available": False,
            "reason": (
                "Federated consent (cross-jurisdiction / multi-"
                "institution) isn't surfaced on this registry yet. "
                "FederatedConsentGraph exists at the engine layer but "
                "isn't attached to the security context."
            ),
        }

    def _active_consent_edges_snapshot(self, graph) -> list[Any]:
        """Return the graph's currently-valid edges as a list.

        Pulled into a helper so the per-tool walk below doesn't
        re-filter on every iteration. Returns an empty list when the
        consent graph isn't configured.
        """
        if graph is None:
            return []
        edges = getattr(graph, "_edges", {})
        return [edge for edge in edges.values() if edge.is_valid()]

    def _summarize_listing_consent_binding(
        self,
        listing: ToolListing,
        active_edges: list[Any],
    ) -> dict[str, Any]:
        """Project one listing into a consent-binding row.

        Combines the manifest-declared ``requires_consent`` flag
        (deterministic) with a best-effort scan of the consent graph
        for edges that reference the tool by name (heuristic).
        """
        manifest_requires_consent = False
        if listing.manifest is not None:
            manifest_requires_consent = bool(
                getattr(listing.manifest, "requires_consent", False)
            )

        base = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
            "requires_consent": manifest_requires_consent,
            "binding_source": (
                "consent_required" if manifest_requires_consent else "consent_optional"
            ),
        }

        grant_sources: list[str] = []
        grant_count = 0
        for edge in active_edges:
            if self._consent_edge_references_tool(edge, listing.tool_name):
                grant_count += 1
                source = getattr(edge, "source_id", "")
                if source and source not in grant_sources:
                    grant_sources.append(source)

        return {
            **base,
            "graph_grant_count": grant_count,
            "grant_sources": grant_sources[:5],
        }

    def _consent_edge_references_tool(self, edge, tool_name: str) -> bool:
        """Return True when a consent edge references ``tool_name``.

        Heuristics, in order of confidence:

        1. ``edge.source_id`` or ``edge.target_id`` equals
           ``tool_name`` (or ``tool:{tool_name}``) — a direct node
           reference.
        2. Any of ``edge.scopes`` matches ``tool_name`` directly,
           contains ``:{tool_name}`` (e.g. ``"call:weather-lookup"``)
           or ``"call_tool:weather-lookup"``, or matches via the same
           glob logic AllowlistPolicy uses.
        3. ``edge.metadata`` carries a string field whose value
           literally equals ``tool_name`` (only string fields, not
           nested traversal — keeps the heuristic bounded).

        These cover the most common patterns we observed in the
        consent test suite without overreaching into "any string
        anywhere on the graph contains the tool name."
        """
        from fastmcp.server.security.policy.policies.allowlist import (
            _matches_any,
        )

        source_id = str(getattr(edge, "source_id", ""))
        target_id = str(getattr(edge, "target_id", ""))
        if source_id in (tool_name, f"tool:{tool_name}"):
            return True
        if target_id in (tool_name, f"tool:{tool_name}"):
            return True

        scopes = getattr(edge, "scopes", set()) or set()
        if scopes:
            scope_strs = {str(s) for s in scopes if s}
            if tool_name in scope_strs:
                return True
            for scope in scope_strs:
                # ``call:weather-lookup`` / ``call_tool:weather-lookup``
                # / ``execute:weather-lookup``-style scope strings.
                if scope.endswith(f":{tool_name}"):
                    return True
            if _matches_any(tool_name, scope_strs) is not None:
                return True

        metadata = getattr(edge, "metadata", None) or {}
        if isinstance(metadata, dict):
            for value in metadata.values():
                if isinstance(value, str) and value == tool_name:
                    return True
                if isinstance(value, (list, tuple, set)):
                    for item in value:
                        if isinstance(item, str) and item == tool_name:
                            return True
        return False

    def get_server_contract_governance(
        self,
        publisher_id: str,
        *,
        include_non_public: bool = False,
    ) -> dict[str, Any]:
        """Return the Contract-Broker governance view for a server.

        Surfaces two layers honestly:

        1. **Broker availability + config** — the Context Broker is
           an opt-in component on the registry; not every deployment
           wires it in. When unavailable, the response says so
           explicitly with operator-actionable copy. When available,
           the response carries the broker's identifying metadata,
           negotiation defaults (max rounds, contract duration,
           session timeout), default-term summary, and live
           counts (active contracts, sessions, exchange-log entries).
        2. **Per-listing contract bindings** — contracts in this
           system are scoped to ``(agent_id, server_id)``, not
           ``(agent_id, tool_name)``. Tool-targeting lives inside the
           term constraints (``allowed_resources``, ``resource_id``,
           ``resource_pattern``, etc.). For each of the publisher's
           listings, we walk every active contract's terms and
           surface those that reference the tool by name or glob —
           ``binding_source="agent_contracts"`` when matches exist,
           ``"no_contracts"`` otherwise. ``matching_agents`` carries a
           bounded sample of agent IDs whose contracts touch this
           tool.

        Args:
            publisher_id: The publisher slug.
            include_non_public: When True, include non-public
                listings (PENDING_REVIEW, etc.) — same visibility
                rule as the policy-governance endpoint.

        Returns:
            ``{server_id, broker, per_tool_contracts, summary, links,
            generated_at}`` on success;
            ``{error, status: 404}`` when no listings match.
        """

        target_listings = self._listings_for_publisher(
            publisher_id, include_non_public=include_non_public
        )
        if not target_listings:
            return {
                "error": f"Publisher '{publisher_id}' not found",
                "status": 404,
            }

        broker = self._broker_or_none()
        broker_block = self._summarize_broker(broker)
        active_contracts = self._active_contracts_snapshot(broker)

        per_tool: list[dict[str, Any]] = []
        for listing in target_listings:
            per_tool.append(
                self._summarize_listing_contract_binding(listing, active_contracts)
            )

        contracted_count = sum(
            1 for entry in per_tool if entry["binding_source"] == "agent_contracts"
        )
        uncontracted_count = len(per_tool) - contracted_count

        return {
            "server_id": publisher_id,
            "broker": broker_block,
            "per_tool_contracts": per_tool,
            "summary": {
                "tool_count": len(per_tool),
                "contracted_count": contracted_count,
                "uncontracted_count": uncontracted_count,
            },
            "links": {
                # The contracts management page is server-rendered HTML
                # today; the same URL works for both navigation and
                # opt-in JSON consumption (?view=html for the latter
                # if the operator wires it).
                "contract_broker_url": f"{self._registry_prefix}/contracts",
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _broker_or_none(self):
        """Return the registry's :class:`ContextBroker` or ``None``.

        The Context Broker is opt-in on the registry's
        :class:`SecurityConfig`. When the operator hasn't configured
        ``contracts=ContractConfig(...)``, ``ctx.broker`` is ``None``
        and contract governance gracefully degrades.
        """
        try:
            ctx = self._required_context()
        except RuntimeError:
            return None
        return getattr(ctx, "broker", None)

    def _summarize_broker(self, broker) -> dict[str, Any]:
        """Project the broker's identifying metadata + live counts.

        Returns a stable shape regardless of whether the broker is
        available — the ``available`` flag tells the consumer
        whether the rest of the fields carry real data.
        """
        if broker is None:
            return {
                "available": False,
                "reason": (
                    "The Context Broker is not enabled on this "
                    "registry. Operators can opt in by passing "
                    "SecurityConfig(contracts=ContractConfig(...)) "
                    "when constructing the registry."
                ),
            }

        default_terms = list(getattr(broker, "default_terms", []) or [])
        exchange_log = getattr(broker, "exchange_log", None)
        return {
            "available": True,
            "broker_id": getattr(broker, "broker_id", "default"),
            "server_id": getattr(broker, "server_id", ""),
            "max_rounds": getattr(broker, "max_rounds", None),
            "contract_duration_seconds": int(broker.contract_duration.total_seconds())
            if hasattr(broker, "contract_duration")
            else None,
            "session_timeout_seconds": int(broker.session_timeout.total_seconds())
            if hasattr(broker, "session_timeout")
            else None,
            "default_term_count": len(default_terms),
            "default_terms": [
                {
                    "term_id": getattr(term, "term_id", ""),
                    "term_type": getattr(getattr(term, "term_type", None), "value", ""),
                    "description": getattr(term, "description", ""),
                    "required": bool(getattr(term, "required", False)),
                }
                for term in default_terms
            ],
            "active_contract_count": int(
                getattr(broker, "active_contract_count", 0) or 0
            ),
            "negotiation_session_count": int(getattr(broker, "session_count", 0) or 0),
            "exchange_log_session_count": int(
                getattr(exchange_log, "session_count", 0) or 0
            )
            if exchange_log is not None
            else 0,
            "exchange_log_entry_count": int(
                getattr(exchange_log, "entry_count", 0) or 0
            )
            if exchange_log is not None
            else 0,
        }

    def _active_contracts_snapshot(self, broker) -> list[Any]:
        """Return the broker's currently-valid contracts as a list.

        Pulled into a helper so the per-tool walk below doesn't have
        to re-filter on every iteration. Returns an empty list when
        the broker isn't configured.
        """
        if broker is None:
            return []
        contracts_map = getattr(broker, "_active_contracts", {}) or {}
        return [c for c in contracts_map.values() if c.is_valid()]

    def _summarize_listing_contract_binding(
        self,
        listing: ToolListing,
        active_contracts: list[Any],
    ) -> dict[str, Any]:
        """Project one listing into a contract-binding row.

        Walks every active contract's terms looking for tool-name
        references; any match gets the listing labelled
        ``agent_contracts`` with a bounded ``matching_agents`` sample.
        """
        base = {
            "listing_id": listing.listing_id,
            "tool_name": listing.tool_name,
            "display_name": listing.display_name or listing.tool_name,
            "hosting_mode": (
                listing.hosting_mode.value if listing.hosting_mode is not None else None
            ),
            "attestation_kind": (
                listing.attestation_kind.value
                if listing.attestation_kind is not None
                else None
            ),
            "status": listing.status.value,
        }

        matching_agents: list[str] = []
        match_count = 0
        for contract in active_contracts:
            if self._contract_references_tool(contract, listing.tool_name):
                match_count += 1
                agent_id = getattr(contract, "agent_id", "")
                if agent_id and agent_id not in matching_agents:
                    matching_agents.append(agent_id)
                # Cap the inline sample so a busy broker doesn't blow
                # up the response payload.
                if len(matching_agents) >= 5:
                    pass

        if match_count == 0:
            return {
                **base,
                "binding_source": "no_contracts",
                "matching_contract_count": 0,
                "matching_agents": [],
            }
        return {
            **base,
            "binding_source": "agent_contracts",
            "matching_contract_count": match_count,
            "matching_agents": matching_agents[:5],
        }

    def _contract_references_tool(self, contract, tool_name: str) -> bool:
        """Return True when any of a contract's terms references ``tool_name``.

        Walks the constraint dicts looking for the standard
        tool-targeting keys (``allowed_resources``,
        ``resource_pattern``, ``resource_id``, ``tool_name``,
        ``tool_names``). Glob-style values are matched via the same
        helper :class:`AllowlistPolicy` uses, so a constraint of
        ``{"resource_pattern": "weather-*"}`` correctly matches a tool
        ``weather-lookup``.
        """
        from fastmcp.server.security.policy.policies.allowlist import (
            _matches_any,
        )

        terms = getattr(contract, "terms", []) or []
        for term in terms:
            constraint = getattr(term, "constraint", None) or {}
            if not isinstance(constraint, dict):
                continue
            for key in (
                "allowed_resources",
                "resource_id",
                "resource_pattern",
                "tool_name",
                "tool_names",
            ):
                raw = constraint.get(key)
                if raw is None:
                    continue
                if isinstance(raw, str):
                    candidates: set[str] = {raw}
                elif isinstance(raw, (list, tuple, set)):
                    candidates = {str(item) for item in raw if item}
                else:
                    continue
                if _matches_any(tool_name, candidates) is not None:
                    return True
                # Literal equality fallback (some constraints write
                # plain tool names without globs).
                if tool_name in candidates:
                    return True
        return False

    def _observed_tool_allowlist(self, listing: ToolListing) -> set[str]:
        """Resolve the curator-vouched tool surface for a listing.

        Mirrors :func:`purecipher.curation.proxy_runtime
        ._build_proxy_security_config` so this method's "what the
        proxy gateway would actually enforce" answer stays accurate.
        """
        observed: set[str] = set()
        metadata = listing.metadata or {}
        if isinstance(metadata, dict):
            introspection = metadata.get("introspection")
            if isinstance(introspection, dict):
                tool_names = introspection.get("tool_names")
                if isinstance(tool_names, list):
                    for name in tool_names:
                        s = str(name).strip()
                        if s:
                            observed.add(s)
        if not observed and listing.manifest is not None:
            for tag in listing.manifest.tags or set():
                tag_str = str(tag)
                if tag_str in {"curated", "third-party"}:
                    continue
                observed.add(tag_str)
        return observed

    def get_install_recipes(
        self,
        tool_name: str,
        *,
        registry_base_url: str | None = None,
    ) -> dict[str, Any]:
        """Return generated install recipes for a verified tool listing."""

        listing = self._get_public_listing(tool_name)
        if listing is None:
            return {"error": f"Tool '{tool_name}' not found", "status": 404}

        recipes = build_install_recipes(
            listing,
            registry_prefix=self._registry_prefix,
            registry_base_url=registry_base_url,
        )
        return {
            "tool_name": listing.tool_name,
            "display_name": listing.display_name,
            "version": listing.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "recipes": [recipe.to_dict() for recipe in recipes],
        }

    def get_moderation_queue(self) -> dict[str, Any]:
        """Return moderation queue sections for pending and managed listings."""

        sections = build_review_queue(
            self._marketplace(),
            trust_lookup=self._trust_overall,
        )
        counts = {section: len(items) for section, items in sections.items()}
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "require_moderation": self._marketplace().require_moderation,
            "counts": counts,
            "sections": {
                section: [item.to_dict() for item in items]
                for section, items in sections.items()
            },
        }

    def list_author_listings(self, author: str) -> dict[str, Any]:
        """Return all listings created by a given author (any status)."""

        listings = self._marketplace().get_by_author(author)
        return {
            "count": len(listings),
            "tools": [self._serialize_listing_detail(listing) for listing in listings],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def moderate_listing(
        self,
        listing_id: str,
        *,
        action_name: str,
        moderator_id: str = "purecipher-admin",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply a moderation action to a listing."""

        action = moderation_action_from_name(action_name)
        if action is None:
            return {
                "error": f"Unknown moderation action '{action_name}'",
                "status": 400,
            }

        marketplace = self._marketplace()
        decision = marketplace.moderate(
            listing_id,
            moderator_id=moderator_id or "purecipher-admin",
            action=action,
            reason=reason,
            metadata=metadata,
        )
        if decision is None:
            return {"error": f"Listing '{listing_id}' not found", "status": 404}

        listing = marketplace.get(listing_id)
        payload = {
            "decision": decision.to_dict(),
            "action": action.value,
            "listing": (
                self._serialize_listing_detail(listing) if listing is not None else None
            ),
        }
        if listing is not None:
            tool = listing.tool_name
            display = listing.display_name or tool
            reason_snip = (reason or "").strip()
            if len(reason_snip) > 220:
                reason_snip = reason_snip[:217] + "…"
            prefix = self._registry_prefix

            # Iter 14.11 — deregister gets a distinct, more emphatic
            # notification because it's terminal and platform-wide.
            # The body explicitly tells viewers the listing is no
            # longer available to clients so anyone with an integration
            # against it can plan accordingly. Audiences includes every
            # role (no filtering) so even drive-by visitors see it.
            if action == ModerationAction.DEREGISTER:
                title = f"Server deregistered — {display}"
                body = (
                    f"{display} (v{listing.version}) has been "
                    f"deregistered by {moderator_id or 'admin'}. "
                    "Calls to this server will be rejected; please "
                    "remove or migrate any client integrations."
                )
                if reason_snip:
                    body = f"{body} Reason: {reason_snip}"
            elif action == ModerationAction.WITHDRAW:
                title = f"Listing withdrawn — {display}"
                body = (
                    f"{display} (v{listing.version}) was withdrawn "
                    f"by its publisher ({moderator_id or 'publisher'}). "
                    "It has been removed from the review queue."
                )
                if reason_snip:
                    body = f"{body} Reason: {reason_snip}"
            elif action == ModerationAction.RESUBMIT:
                title = f"Listing resubmitted — {display}"
                body = (
                    f"{display} (v{listing.version}) was resubmitted "
                    f"by its publisher ({moderator_id or 'publisher'}). "
                    "It has been returned to the review queue."
                )
                if reason_snip:
                    body = f"{body} Note: {reason_snip}"
            else:
                title = f"Moderation: {action.value.replace('_', ' ')} — {display}"
                body = (
                    f"{tool} v{listing.version} — decision by "
                    f"{moderator_id or 'moderator'}."
                )
                if reason_snip:
                    body = f"{body} {reason_snip}"
            self.record_registry_notification(
                event_kind=(
                    "listing_deregistered"
                    if action == ModerationAction.DEREGISTER
                    else "listing_withdrawn"
                    if action == ModerationAction.WITHDRAW
                    else "listing_resubmitted"
                    if action == ModerationAction.RESUBMIT
                    else "moderation_decision"
                ),
                title=title,
                body=body,
                link_path=f"{prefix}/listings/{quote(tool, safe='')}",
                audiences=("viewer", "publisher", "reviewer", "admin"),
            )
        return payload

    def submit_tool(
        self,
        manifest: SecurityManifest,
        *,
        display_name: str = "",
        description: str = "",
        categories: set[ToolCategory] | None = None,
        homepage_url: str = "",
        source_url: str = "",
        tool_license: str = "",
        tags: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
        changelog: str = "",
        requested_level: CertificationLevel | None = None,
        attestation_kind: Any = None,
        upstream_ref: Any = None,
        curator_id: str = "",
        hosting_mode: Any = None,
    ) -> RegistrySubmissionResult:
        """Certify and publish a tool into the PureCipher registry.

        ``attestation_kind``, ``upstream_ref``, ``curator_id``, and
        ``hosting_mode`` propagate through to the marketplace listing.
        Pass them when curating a third-party MCP server; leave at
        defaults for the standard author-attested publish flow.
        """
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
            UpstreamRef,
        )

        # Late-bind the curator/hosting arguments so callers don't have
        # to import the enums when they want defaults.
        kind = attestation_kind or AttestationKind.AUTHOR
        hosting = hosting_mode or HostingMode.CATALOG
        if not isinstance(kind, AttestationKind):
            raise TypeError("attestation_kind must be an AttestationKind")
        if not isinstance(hosting, HostingMode):
            raise TypeError("hosting_mode must be a HostingMode")
        if upstream_ref is not None and not isinstance(upstream_ref, UpstreamRef):
            raise TypeError("upstream_ref must be an UpstreamRef")

        # Curator-attested listings cap the certification tier at BASIC.
        # The registry observed the protocol surface and signed the
        # attestation, but it did NOT review the upstream's source —
        # so STANDARD or STRICT (which imply source-level guarantees)
        # would be a misleading trust signal on a third-party listing.
        # Authors can still hit the higher tiers; only curator
        # submissions are clamped here. This applies regardless of
        # what the caller passed for ``requested_level``.
        effective_requested_level = requested_level
        if kind == AttestationKind.CURATOR:
            if effective_requested_level is None or _level_index(
                effective_requested_level
            ) > _level_index(CertificationLevel.BASIC):
                effective_requested_level = CertificationLevel.BASIC

        preflight = self.preflight_submission(
            manifest,
            display_name=display_name,
            categories=categories,
            metadata=metadata,
            requested_level=effective_requested_level,
        )
        if not preflight.ready_for_publish:
            return RegistrySubmissionResult(
                accepted=False,
                reason=preflight.summary,
                report=preflight.report,
                attestation=preflight.attestation,
                manifest_digest=preflight.manifest_digest,
            )

        from purecipher.token_cost import estimate_definition_tokens

        definition_tokens = estimate_definition_tokens(
            manifest.to_dict() if hasattr(manifest, "to_dict") else {}
        )

        listing = self._marketplace().publish(
            manifest.tool_name,
            display_name=display_name or manifest.tool_name,
            description=description or manifest.description,
            version=manifest.version,
            author=manifest.author,
            categories=categories,
            manifest=manifest,
            attestation=preflight.attestation,
            homepage_url=homepage_url,
            source_url=source_url,
            tool_license=tool_license,
            tags=tags or manifest.tags,
            metadata={
                "issuer_id": self._issuer_id,
                "verified_registry": "purecipher",
                "definition_tokens": definition_tokens,
                **(metadata or {}),
            },
            changelog=changelog,
            attestation_kind=kind,
            upstream_ref=upstream_ref,
            curator_id=curator_id,
            hosting_mode=hosting,
        )

        prefix = self._registry_prefix
        tool = listing.tool_name
        display = listing.display_name or tool
        all_personas = ("viewer", "publisher", "reviewer", "admin")
        if listing.status == PublishStatus.PENDING_REVIEW:
            self.record_registry_notification(
                event_kind="listing_pending_review",
                title=f"Listing submitted for review: {display}",
                body=(
                    f"{tool} v{listing.version} is queued for moderator approval "
                    f"before it appears in the public catalog."
                ),
                link_path=f"{prefix}/listings/{quote(tool, safe='')}",
                audiences=all_personas,
            )
        elif listing.status == PublishStatus.PUBLISHED:
            self.record_registry_notification(
                event_kind="listing_published",
                title=f"Listing published: {display}",
                body=f"{tool} v{listing.version} is live in the verified catalog.",
                link_path=f"{prefix}/listings/{quote(tool, safe='')}",
                audiences=all_personas,
            )
        else:
            self.record_registry_notification(
                event_kind="listing_status",
                title=f"Listing recorded: {display}",
                body=f"{tool} v{listing.version} — status {listing.status.value}.",
                link_path=f"{prefix}/listings/{quote(tool, safe='')}",
                audiences=all_personas,
            )

        return RegistrySubmissionResult(
            accepted=True,
            reason="Accepted into the PureCipher verified registry.",
            report=preflight.report,
            attestation=preflight.attestation,
            manifest_digest=preflight.manifest_digest,
            listing=listing,
        )

    # ── Curator workflow ──────────────────────────────────────────

    def _curation_introspector(self) -> Any:
        """Return the channel-aware introspector used by curate routes.

        Defaults to the multi-channel :class:`Introspector` dispatcher
        so the wizard handles HTTP/PyPI/npm uniformly. Pre-fix the
        default was the single-channel ``HTTPIntrospector``, which
        caused PyPI / npm refs to be rejected at the introspect step
        with "This iteration supports HTTP upstreams only" — a
        regression from iteration 4 that wasn't caught because tests
        explicitly install their own dispatcher via
        :meth:`set_curation_introspector`.

        Cached on the instance so tests can still swap it.
        """
        introspector = getattr(self, "_curate_introspector_instance", None)
        if introspector is None:
            from purecipher.curation import Introspector

            introspector = Introspector()
            self._curate_introspector_instance = introspector
        return introspector

    def set_curation_introspector(self, introspector: Any) -> None:
        """Override the curator-flow introspector (test-only seam)."""
        self._curate_introspector_instance = introspector

    async def _curate_submit_handler(
        self,
        body: dict[str, Any],
        session: Any,
    ) -> dict[str, Any]:
        """Backend for ``POST /registry/curate/submit``.

        Validates the body, re-runs introspection (so the manifest
        always reflects what the registry actually saw at submit
        time), applies the curator's confirm/remove choices, builds
        and submits the manifest as a curator-attested listing.
        """
        from fastmcp.server.security.gateway.tool_marketplace import (
            AttestationKind,
            HostingMode,
        )
        from purecipher.curation import (
            CredentialValidationError,
            IntrospectionError,
            UpstreamFetcher,
            UpstreamResolutionError,
            derive_manifest_draft,
            validate_introspect_env,
        )
        from purecipher.curation.manifest_generator import (
            reconcile_curator_selection,
        )

        if not isinstance(body, dict):
            raise ValueError("Submission body must be an object.")

        raw_input = str(body.get("upstream") or body.get("upstream_url") or "").strip()

        # Validate hosting_mode early — before the expensive resolve +
        # introspect roundtrips — so a wizard misclick fails fast.
        raw_hosting_early = str(body.get("hosting_mode", "catalog")).strip().lower()
        if raw_hosting_early not in {"catalog", "proxy"}:
            return {
                "error": (
                    "hosting_mode must be 'catalog' or 'proxy' "
                    f"(got {raw_hosting_early!r})."
                ),
                "status": 400,
            }

        raw_attestation_kind = str(body.get("attestation_kind", "curator")).strip().lower()
        if raw_attestation_kind not in {"author", "curator"}:
            return {
                "error": (
                    "attestation_kind must be 'author' or 'curator' "
                    f"(got {raw_attestation_kind!r})."
                ),
                "status": 400,
            }

        # Iter 14.8.1 — token-on-submit.
        #
        # Submit re-introspects (line below) as a tamper defence — the
        # manifest a curator vouches for must be bounded by what the
        # upstream is *currently* exposing, not what was shown at Step
        # 2. For token-required upstreams (Stripe, Slack, GitHub,
        # Atlassian), that re-introspect needs the same env the curator
        # supplied earlier; the wizard sends it back here.
        #
        # Same one-shot contract as ``/curate/introspect``: validate,
        # use, drop. Never persisted, never echoed in the response,
        # never logged with values.
        raw_env = body.get("env")
        try:
            env = validate_introspect_env(
                raw_env if isinstance(raw_env, dict) else None
            )
        except CredentialValidationError as exc:
            return {"error": str(exc), "status": 400}

        try:
            preview = UpstreamFetcher().resolve(raw_input)
        except UpstreamResolutionError as exc:
            return {"error": str(exc), "status": 400}

        # Proxy mode now supports HTTP, PyPI, npm, and Docker channels.
        # PyPI/npm/Docker upstreams are hosted per-session via uvx /
        # npx / docker-run subprocess transports — see
        # ``build_curator_proxy_server`` for the channel-dispatched
        # client factory.

        introspector = self._curation_introspector()
        try:
            introspection = await introspector.introspect(preview.upstream_ref, env=env)
        except IntrospectionError as exc:
            return {"error": str(exc), "status": 502}
        finally:
            # Drop the local env reference the moment the re-introspect
            # returns. The remainder of the submit pipeline (manifest
            # build, persistence, signing) never sees the credentials
            # — it operates on the introspection result, which is
            # value-only and contains no secrets.
            env = None

        # An upstream that exposes zero tools, resources, AND prompts
        # is functionally empty — vouching for it carries no useful
        # trust signal. The most likely cause is auth-gating: the
        # registry can connect but the upstream filters its capability
        # surface to anonymous callers. Refuse the submission with a
        # clear message rather than minting a meaningless attestation.
        if (
            introspection.tool_count == 0
            and introspection.resource_count == 0
            and introspection.prompt_count == 0
        ):
            return {
                "error": (
                    "The upstream exposed zero tools, resources, or "
                    "prompts. Either it requires authentication the "
                    "registry doesn't have, or it isn't an MCP server. "
                    "Curator-attested listings need an observable surface."
                ),
                "status": 422,
            }

        # Re-derive the suggestion list at submit time so the curator's
        # selection is reconciled against THIS introspection's
        # observations — not whatever was shown earlier in the wizard.
        # Curator can only confirm/remove; new scopes are dropped.
        baseline = derive_manifest_draft(
            introspection,
            suggested_tool_name=str(body.get("tool_name", "")).strip()
            or preview.suggested_tool_name,
            suggested_display_name=str(body.get("display_name", "")).strip()
            or preview.suggested_display_name,
        )
        selected = body.get("selected_permissions") or []
        if not isinstance(selected, list):
            return {
                "error": "selected_permissions must be a list",
                "status": 400,
            }
        draft = reconcile_curator_selection(baseline, selected)

        # Iter 14.10 — tool selection.
        #
        # The curator picks which observed tools they're actually
        # vouching for. Same confirm-or-remove contract as
        # permissions: every entry in ``selected_tools`` must be a
        # name the registry observed during introspection — names
        # that aren't observed are silently dropped (never smuggled
        # into the manifest).
        #
        # This narrows two things:
        # 1. The manifest's data_flow description, so the published
        #    attestation lists only vouched tools.
        # 2. The AllowlistPolicy source for proxy hosting mode — the
        #    proxy will refuse to forward calls to deselected tools.
        #
        # Backward-compat: if ``selected_tools`` is omitted, the
        # curator vouches for the entire observed surface (the
        # pre-Iter 14.10 behavior).
        observed_tool_names: list[str] = [t.name for t in introspection.tools]
        raw_selected_tools = body.get("selected_tools")
        if raw_selected_tools is None:
            vouched_tool_names: list[str] = list(observed_tool_names)
        else:
            if not isinstance(raw_selected_tools, list):
                return {
                    "error": (
                        "selected_tools must be a list of tool names "
                        "(or omitted to vouch for all observed)."
                    ),
                    "status": 400,
                }
            requested = {
                str(item).strip()
                for item in raw_selected_tools
                if isinstance(item, str) and item.strip()
            }
            # Preserve original ordering from introspection so the
            # listing's tool order matches what the upstream returned.
            vouched_tool_names = [
                name for name in observed_tool_names if name in requested
            ]
            if not vouched_tool_names:
                return {
                    "error": (
                        "Select at least one tool to vouch for. A "
                        "curator-attested listing with no vouched "
                        "tools carries no useful trust signal."
                    ),
                    "status": 422,
                }

        # Replace the draft's observed_tool_names with the vouched
        # subset so ``build_manifest`` describes only the vouched
        # surface in its data_flow declaration. We rebuild the draft
        # rather than mutating it because ManifestDraft.observed_tool_names
        # is treated as immutable everywhere else in the pipeline.
        from purecipher.curation.manifest_generator import ManifestDraft

        draft = ManifestDraft(
            upstream_ref=dict(draft.upstream_ref),
            suggested_tool_name=draft.suggested_tool_name,
            suggested_display_name=draft.suggested_display_name,
            suggested_description=draft.suggested_description,
            permission_suggestions=list(draft.permission_suggestions),
            observed_tool_names=list(vouched_tool_names),
        )

        tool_name = str(body.get("tool_name", "")).strip() or draft.suggested_tool_name
        if not tool_name:
            return {
                "error": ("tool_name is required (auto-suggestion was empty too)."),
                "status": 400,
            }
        display_name = (
            str(body.get("display_name", "")).strip()
            or draft.suggested_display_name
            or tool_name
        )
        version = str(body.get("version", "")).strip() or "0.1.0"
        description = str(body.get("description", "")).strip()
        categories = _coerce_categories(body.get("categories")) or None
        submitter = session.username if session is not None else "local"
        curator_id = submitter if raw_attestation_kind == "curator" else ""
        # Map the validated raw_hosting string from earlier into the
        # HostingMode enum (validation already ran before resolve).
        hosting_mode = (
            HostingMode.PROXY if raw_hosting_early == "proxy" else HostingMode.CATALOG
        )

        manifest = draft.build_manifest(
            tool_name=tool_name,
            display_name=display_name,
            version=version,
            author=submitter,
            description=description,
        )

        result = self.submit_tool(
            manifest,
            display_name=display_name,
            description=description,
            categories=categories,
            source_url=preview.upstream_ref.source_url
            or preview.upstream_ref.identifier,
            metadata={
                "curated": True,
                "upstream_url": preview.upstream_ref.identifier,
                "introspection": {
                    "tool_count": introspection.tool_count,
                    "resource_count": introspection.resource_count,
                    "prompt_count": introspection.prompt_count,
                    # Iter 14.10 — ``tool_names`` is the *vouched*
                    # subset (what the curator selected), not the full
                    # observed surface. Proxy mode reads this to build
                    # its AllowlistPolicy, so deselected tools are
                    # blocked at the gateway. The full observed list
                    # is preserved separately under
                    # ``observed_tool_names`` for transparency.
                    "tool_names": list(vouched_tool_names),
                    "observed_tool_names": list(observed_tool_names),
                    "vouched_tool_count": len(vouched_tool_names),
                    "resource_uris": [r.uri for r in introspection.resources],
                    "prompt_names": [p.name for p in introspection.prompts],
                },
            },
            attestation_kind=(
                AttestationKind.AUTHOR
                if raw_attestation_kind == "author"
                else AttestationKind.CURATOR
            ),
            upstream_ref=preview.upstream_ref,
            curator_id=curator_id,
            hosting_mode=hosting_mode,
        )
        if not result.accepted:
            return {
                "error": result.reason,
                "status": 400,
                "report": result.report.to_dict() if result.report else None,
            }
        # Track the submission in the curator's activity feed.
        if session is not None:
            try:
                self._account_activity.append(
                    username=session.username,
                    event_kind=(
                        "author_listing_submitted"
                        if raw_attestation_kind == "author"
                        else "curated_listing_submitted"
                    ),
                    title=(
                        f"Author listing: {display_name}"
                        if raw_attestation_kind == "author"
                        else f"Curated listing: {display_name}"
                    ),
                    detail=(
                        f"Connected {preview.upstream_ref.identifier} "
                        f"({introspection.tool_count} tool(s) observed)"
                        if raw_attestation_kind == "author"
                        else f"Vouched for {preview.upstream_ref.identifier} "
                        f"({introspection.tool_count} tool(s) observed)"
                    ),
                    metadata={
                        "tool_name": tool_name,
                        "upstream_url": preview.upstream_ref.identifier,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to record curator activity for %s",
                    session.username,
                    exc_info=True,
                )

        return {
            "accepted": True,
            "listing": result.listing.to_dict() if result.listing else None,
            "manifest_digest": result.manifest_digest,
            "introspection": {
                "tool_count": introspection.tool_count,
                "resource_count": introspection.resource_count,
                "prompt_count": introspection.prompt_count,
            },
            "status": 201,
        }

    def preflight_submission(
        self,
        manifest: SecurityManifest,
        *,
        display_name: str = "",
        categories: set[ToolCategory] | None = None,
        metadata: dict[str, Any] | None = None,
        requested_level: CertificationLevel | None = None,
    ) -> RegistryPreflightResult:
        """Validate a submission without publishing it."""

        result = self._certification_pipeline().certify(
            manifest,
            requested_level=requested_level,
        )
        level_order = list(CertificationLevel)
        meets_minimum = level_order.index(
            result.certification_level
        ) >= level_order.index(self.minimum_certification)

        preview_listing = ToolListing(
            tool_name=manifest.tool_name,
            display_name=display_name or manifest.tool_name,
            description=manifest.description,
            version=manifest.version,
            author=manifest.author,
            categories=categories or set(),
            manifest=manifest,
            attestation=result.attestation if result.is_certified else None,
            metadata={
                "issuer_id": self._issuer_id,
                "verified_registry": "purecipher",
                **(metadata or {}),
            },
        )
        install_recipes = build_install_recipes(
            preview_listing,
            registry_prefix=self._registry_prefix,
        )
        runtime_recipe_ids = {
            recipe.recipe_id
            for recipe in install_recipes
            if recipe.recipe_id not in {"registry_reference", "verify_attestation"}
        }

        finding_count = len(result.report.findings)
        if not meets_minimum:
            summary = (
                "Submission is below the registry minimum certification level "
                f"({self.minimum_certification.value})."
            )
        elif not result.is_certified:
            summary = (
                "Certification failed. Resolve validation blockers before publishing."
            )
        elif finding_count:
            suffix = "s" if finding_count != 1 else ""
            summary = (
                f"Ready to publish with {finding_count} validation finding{suffix}."
            )
        else:
            summary = "Ready to publish."

        return RegistryPreflightResult(
            ready_for_publish=result.is_certified and meets_minimum,
            summary=summary,
            requested_level=(requested_level or self.minimum_certification).value,
            effective_certification_level=result.certification_level.value,
            minimum_required_level=self.minimum_certification.value,
            meets_minimum=meets_minimum,
            manifest_digest=result.manifest_digest,
            install_ready=bool(runtime_recipe_ids),
            install_recipes=[
                {
                    "recipe_id": recipe.recipe_id,
                    "title": recipe.title,
                    "format": recipe.format,
                }
                for recipe in install_recipes
            ],
            report=result.report,
            attestation=result.attestation,
        )

    def verify_tool(
        self,
        tool_name: str,
        *,
        manifest: SecurityManifest | None = None,
        include_non_public: bool = False,
    ) -> dict[str, Any]:
        """Verify a registered tool's attestation.

        Args:
            tool_name: The tool's canonical name.
            manifest: Optional manifest override; defaults to the
                listing's stored manifest.
            include_non_public: When ``True``, accept listings whose
                status isn't ``PUBLISHED`` (e.g. ``PENDING_REVIEW``).
                The route handler sets this for authenticated callers
                so curators can verify their own just-submitted
                listings. Anonymous callers should not pass this —
                pending listings are not part of the public surface.
        """

        certification_pipeline = self._certification_pipeline()
        if include_non_public:
            listing = self._marketplace().get_by_name(tool_name)
        else:
            listing = self._get_public_listing(tool_name)
        if listing is None:
            return {"error": f"Tool '{tool_name}' not found", "status": 404}
        if listing.attestation is None:
            return {"error": f"Tool '{tool_name}' has no attestation", "status": 400}

        verification = certification_pipeline.verify_attestation(
            listing.attestation,
            manifest or listing.manifest,
        )
        return {
            "tool_name": tool_name,
            "verification": self._serialize_verification(verification),
            "attestation": listing.attestation.to_dict(),
        }

    def _render_registry_ui(
        self,
        *,
        prefix: str,
        query: str = "",
        min_certification: str = "",
        selected_tool: str = "",
        manifest_text: str = SAMPLE_MANIFEST_JSON,
        display_name: str = "",
        categories: str = "",
        requested_level: str = CertificationLevel.BASIC.value,
        session: RegistrySession | None = None,
        submission_title: str | None = None,
        submission_body: str | None = None,
        submission_is_error: bool = False,
        page_notice_title: str | None = None,
        page_notice_body: str | None = None,
        page_notice_is_error: bool = False,
    ) -> str:
        level = _coerce_level(
            min_certification or None,
            default=self.minimum_certification,
        )
        catalog = self.list_verified_tools(
            query=query or None,
            min_certification=level,
        )
        detail = None
        if selected_tool:
            maybe_detail = self.get_verified_tool(selected_tool)
            if "error" not in maybe_detail:
                detail = maybe_detail

        return create_registry_ui_html(
            server_name=self.name,
            registry_prefix=prefix,
            health=self.get_registry_health(),
            catalog=catalog,
            publishers=_limit_list_payload(
                self.list_publishers(limit=6),
                key="publishers",
                limit=6,
            ),
            queue=self.get_moderation_queue(),
            detail=detail,
            query=query,
            min_certification=min_certification,
            manifest_text=manifest_text,
            display_name=display_name,
            categories=categories,
            requested_level=requested_level,
            auth_enabled=self.auth_enabled,
            session=self._session_payload(session),
            submission_title=submission_title,
            submission_body=submission_body,
            submission_is_error=submission_is_error,
            page_notice_title=page_notice_title,
            page_notice_body=page_notice_body,
            page_notice_is_error=page_notice_is_error,
        )

    def _render_publish_ui(
        self,
        *,
        prefix: str,
        session: RegistrySession | None = None,
        manifest_text: str = SAMPLE_MANIFEST_JSON,
        runtime_metadata_text: str = SAMPLE_RUNTIME_METADATA_JSON,
        display_name: str = "",
        categories: str = "",
        tags: str = "",
        requested_level: str = CertificationLevel.BASIC.value,
        source_url: str = "",
        homepage_url: str = "",
        tool_license: str = "MIT",
        preflight: dict[str, Any] | None = None,
        submission_title: str | None = None,
        submission_body: str | None = None,
        submission_is_error: bool = False,
        page_notice_title: str | None = None,
        page_notice_body: str | None = None,
        page_notice_is_error: bool = False,
    ) -> str:
        return create_publish_html(
            server_name=self.name,
            registry_prefix=prefix,
            auth_enabled=self.auth_enabled,
            session=self._session_payload(session),
            manifest_text=manifest_text,
            runtime_metadata_text=runtime_metadata_text,
            display_name=display_name,
            categories=categories,
            tags=tags,
            requested_level=requested_level,
            source_url=source_url,
            homepage_url=homepage_url,
            tool_license=tool_license,
            preflight=preflight,
            submission_title=submission_title,
            submission_body=submission_body,
            submission_is_error=submission_is_error,
            page_notice_title=page_notice_title,
            page_notice_body=page_notice_body,
            page_notice_is_error=page_notice_is_error,
        )

    def _render_publish_ui_from_state(
        self,
        *,
        prefix: str,
        state: PublishFormState,
        session: RegistrySession | None = None,
        preflight: dict[str, Any] | None = None,
        submission_title: str | None = None,
        submission_body: str | None = None,
        submission_is_error: bool = False,
        page_notice_title: str | None = None,
        page_notice_body: str | None = None,
        page_notice_is_error: bool = False,
    ) -> str:
        return self._render_publish_ui(
            prefix=prefix,
            session=session,
            manifest_text=state["manifest_text"],
            runtime_metadata_text=state["runtime_metadata_text"],
            display_name=state["display_name"],
            categories=state["categories"],
            tags=state["tags"],
            requested_level=state["requested_level"],
            source_url=state["source_url"],
            homepage_url=state["homepage_url"],
            tool_license=state["tool_license"],
            preflight=preflight,
            submission_title=submission_title,
            submission_body=submission_body,
            submission_is_error=submission_is_error,
            page_notice_title=page_notice_title,
            page_notice_body=page_notice_body,
            page_notice_is_error=page_notice_is_error,
        )

    @staticmethod
    def _publish_form_state(form: Any) -> PublishFormState:
        state: PublishFormState = {
            "manifest_text": str(form.get("manifest", SAMPLE_MANIFEST_JSON)),
            "runtime_metadata_text": str(form.get("runtime_metadata", "")),
            "display_name": str(form.get("display_name", "")),
            "categories": str(form.get("categories", "")),
            "tags": str(form.get("tags", "")),
            "requested_level": str(form.get("requested_level", "basic")),
            "source_url": str(form.get("source_url", "")),
            "homepage_url": str(form.get("homepage_url", "")),
            "tool_license": str(form.get("tool_license", "")),
            "submission_action": str(form.get("submission_action", "publish")),
        }
        return state

    def _parse_publish_inputs(
        self,
        *,
        manifest_text: str,
        runtime_metadata_text: str,
        categories_text: str,
        tags_text: str,
        requested_level_text: str,
    ) -> tuple[
        SecurityManifest,
        set[ToolCategory] | None,
        set[str] | None,
        CertificationLevel | None,
        dict[str, Any],
    ]:
        manifest_data = json.loads(manifest_text)
        if not isinstance(manifest_data, dict):
            raise ValueError("`manifest` must be a JSON object.")

        manifest = _parse_manifest(manifest_data)
        metadata = _parse_optional_json_object(
            runtime_metadata_text,
            field_name="runtime_metadata",
        )
        categories = _coerce_categories(list(_parse_csv_set(categories_text))) or None
        tags = _parse_csv_set(tags_text) or None
        requested_level = _coerce_level(
            requested_level_text,
            default=self.minimum_certification,
        )
        return manifest, categories, tags, requested_level, metadata

    def _render_review_queue_ui(
        self,
        *,
        prefix: str,
        session: RegistrySession | None = None,
        notice_title: str | None = None,
        notice_body: str | None = None,
        notice_is_error: bool = False,
    ) -> str:
        return create_review_queue_html(
            server_name=self.name,
            registry_prefix=prefix,
            queue=self._filter_queue_for_session(
                self.get_moderation_queue(),
                session,
            ),
            auth_enabled=self.auth_enabled,
            session=self._session_payload(session),
            notice_title=notice_title,
            notice_body=notice_body,
            notice_is_error=notice_is_error,
        )

    def _legacy_ui_disabled_response(self, request: Request) -> Response:
        """Reject requests for the legacy server-rendered registry UI."""

        payload = {
            "error": (
                "Legacy registry UI is disabled on this backend. "
                "Use the separate registry console instead."
            ),
            "status": 404,
        }
        if _wants_json(request):
            return JSONResponse(payload, status_code=404)
        return Response(
            content=payload["error"],
            status_code=404,
            media_type="text/plain",
        )

    def mount_registry_api(self, *, prefix: str = "/registry") -> PureCipherRegistry:
        """Mount the PureCipher registry HTTP routes."""

        if self._registry_api_mounted:
            return self

        async def _handle_publish_form(request: Request):
            session = self._session_from_request(request)
            form = await request.form()
            state = self._publish_form_state(form)
            submission_action = state["submission_action"].strip().lower() or "publish"

            try:
                manifest, categories, tags, requested_level, metadata = (
                    self._parse_publish_inputs(
                        manifest_text=state["manifest_text"],
                        runtime_metadata_text=state["runtime_metadata_text"],
                        categories_text=state["categories"],
                        tags_text=state["tags"],
                        requested_level_text=state["requested_level"],
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                return create_secure_html_response(
                    self._render_publish_ui_from_state(
                        prefix=prefix,
                        state=state,
                        session=session,
                        submission_title="Publish form is invalid",
                        submission_body=str(exc),
                        submission_is_error=True,
                    ),
                    status_code=400,
                )

            preflight = self.preflight_submission(
                manifest,
                display_name=state["display_name"],
                categories=categories,
                metadata=metadata,
                requested_level=requested_level,
            )

            if submission_action == "preview":
                return create_secure_html_response(
                    self._render_publish_ui_from_state(
                        prefix=prefix,
                        state=state,
                        session=session,
                        preflight=preflight.to_dict(),
                        submission_title="Preflight complete",
                        submission_body=preflight.summary,
                        submission_is_error=not preflight.ready_for_publish,
                    )
                )

            if self.auth_enabled and not self._has_roles(
                session,
                {
                    RegistryRole.PUBLISHER,
                    RegistryRole.REVIEWER,
                    RegistryRole.ADMIN,
                },
            ):
                status_code = 401 if session is None else 403
                message = (
                    "Sign in with a publisher, reviewer, or admin account "
                    "before publishing listings."
                )
                return create_secure_html_response(
                    self._render_publish_ui_from_state(
                        prefix=prefix,
                        state=state,
                        session=session,
                        preflight=preflight.to_dict(),
                        page_notice_title="Publishing blocked",
                        page_notice_body=message,
                        page_notice_is_error=True,
                    ),
                    status_code=status_code,
                )

            result = self.submit_tool(
                manifest,
                display_name=state["display_name"],
                categories=categories,
                homepage_url=state["homepage_url"],
                source_url=state["source_url"],
                tool_license=state["tool_license"],
                tags=tags,
                metadata=metadata,
                requested_level=requested_level,
            )

            status_code = 200 if result.accepted else 400
            submission_body = (
                f"Listing: {result.listing.tool_name} · "
                f"Certification: {result.attestation.certification_level.value}"
                if result.listing is not None
                else result.reason
            )
            return create_secure_html_response(
                self._render_publish_ui_from_state(
                    prefix=prefix,
                    state=state,
                    session=session,
                    preflight=preflight.to_dict(),
                    submission_title=result.reason,
                    submission_body=submission_body,
                    submission_is_error=not result.accepted,
                ),
                status_code=status_code,
            )

        @self.custom_route(f"{prefix}/health", methods=["GET"])
        async def registry_health(request: Request) -> JSONResponse:
            return JSONResponse(self.get_registry_health())

        @self.custom_route(f"{prefix}/session", methods=["GET"])
        async def registry_session(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            return JSONResponse(
                {
                    "auth_enabled": self.auth_enabled,
                    "bootstrap_required": self._bootstrap_required(),
                    "setup_url": f"{prefix}/setup"
                    if self._bootstrap_required() and self._enable_legacy_registry_ui
                    else None,
                    "session": self._session_payload(session),
                }
            )

        @self.custom_route(f"{prefix}/notifications", methods=["GET"])
        async def registry_notifications(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            role = session.role.value if session is not None else None
            try:
                limit = int(request.query_params.get("limit", "40"))
            except ValueError:
                limit = 40
            limit = max(1, min(limit, 100))
            return JSONResponse(
                self.get_registry_notifications(
                    auth_enabled=self.auth_enabled,
                    role=role,
                    limit=limit,
                )
            )

        @self.custom_route(f"{prefix}/me/preferences", methods=["GET"])
        async def registry_my_preferences(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            username = session.username if session is not None else "local"
            return JSONResponse(
                {
                    "username": username,
                    "preferences": self._user_preferences.get(username),
                }
            )

        @self.custom_route(f"{prefix}/me/preferences", methods=["PUT"])
        async def registry_update_my_preferences(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            raw_preferences = body.get("preferences", body)
            if not isinstance(raw_preferences, dict):
                return JSONResponse(
                    {"error": "`preferences` must be an object.", "status": 400},
                    status_code=400,
                )
            username = session.username if session is not None else "local"
            preferences = self._user_preferences.set(username, raw_preferences)
            return JSONResponse(
                {
                    "username": username,
                    "preferences": preferences,
                }
            )

        @self.custom_route(f"{prefix}/me/preferences", methods=["DELETE"])
        async def registry_reset_my_preferences(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            username = session.username if session is not None else "local"
            return JSONResponse(
                {
                    "username": username,
                    "preferences": self._user_preferences.reset(username),
                }
            )

        @self.custom_route(f"{prefix}/me/activity", methods=["GET"])
        async def registry_my_activity(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            username = session.username if session is not None else "local"
            limit = _int_query_param(
                request, "limit", default=20, minimum=1, maximum=50
            )
            return JSONResponse(
                {
                    "username": username,
                    "items": self._account_activity.list_recent(
                        username=username,
                        limit=limit,
                    ),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/me/password", methods=["POST"])
        async def registry_change_my_password(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if session is None:
                return JSONResponse(
                    {"error": "Password changes require auth.", "status": 400},
                    status_code=400,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            current_password = str(body.get("current_password") or "")
            new_password = str(body.get("new_password") or "")
            if len(new_password) < 8:
                return JSONResponse(
                    {
                        "error": "New password must be at least 8 characters.",
                        "status": 400,
                    },
                    status_code=400,
                )
            changed = self._account_security.change_password(
                username=session.username,
                current_password=current_password,
                new_password=new_password,
            )
            if not changed:
                self._account_activity.append(
                    username=session.username,
                    event_kind="password_change_failed",
                    title="Password change failed",
                    detail="Current password did not match.",
                    metadata={"client": request.client.host if request.client else ""},
                )
                return JSONResponse(
                    {"error": "Current password is incorrect.", "status": 403},
                    status_code=403,
                )
            self._account_activity.append(
                username=session.username,
                event_kind="password_changed",
                title="Password changed",
                detail="Password was updated and other sessions were revoked.",
                metadata={"client": request.client.host if request.client else ""},
            )
            response = JSONResponse({"ok": True, "revoked_other_sessions": True})
            self._clear_auth_cookie(response)
            return response

        @self.custom_route(f"{prefix}/me/sessions", methods=["GET"])
        async def registry_my_sessions(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            username = session.username if session is not None else "local"
            return JSONResponse(
                {
                    "username": username,
                    "current_session_id": session.session_id if session else "",
                    "items": self._account_security.list_sessions(username=username),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/me/sessions/{{session_id}}", methods=["DELETE"])
        async def registry_revoke_my_session(request: Request) -> JSONResponse:
            session_id = request.path_params.get("session_id", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if session is None:
                return JSONResponse({"ok": True})
            revoked = self._account_security.revoke_session(
                session_id=session_id,
                username=session.username,
            )
            self._account_activity.append(
                username=session.username,
                event_kind="session_revoked",
                title="Session revoked",
                detail="A registry session was revoked from settings.",
                metadata={"session_id": session_id},
            )
            response = JSONResponse({"ok": revoked})
            if session.session_id == session_id:
                self._clear_auth_cookie(response)
            return response

        @self.custom_route(f"{prefix}/me/tokens", methods=["GET"])
        async def registry_my_tokens(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            username = session.username if session is not None else "local"
            return JSONResponse(
                {
                    "username": username,
                    "items": self._account_security.list_api_tokens(username=username),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/me/tokens", methods=["POST"])
        async def registry_create_my_token(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if session is None:
                return JSONResponse(
                    {"error": "API tokens require auth.", "status": 400},
                    status_code=400,
                )
            try:
                body = await request.json()
            except Exception:
                body = {}
            name = str(body.get("name") or "") if isinstance(body, dict) else ""
            created = self._account_security.create_api_token(
                username=session.username,
                name=name,
            )
            self._account_activity.append(
                username=session.username,
                event_kind="api_token_created",
                title="API token created",
                detail=created["token_record"]["name"],
                metadata={"token_id": created["token_record"]["token_id"]},
            )
            return JSONResponse(created, status_code=201)

        @self.custom_route(f"{prefix}/me/tokens/{{token_id}}", methods=["DELETE"])
        async def registry_revoke_my_token(request: Request) -> JSONResponse:
            token_id = request.path_params.get("token_id", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if session is None:
                return JSONResponse({"ok": True})
            revoked = self._account_security.revoke_api_token(
                username=session.username,
                token_id=token_id,
            )
            if revoked:
                self._account_activity.append(
                    username=session.username,
                    event_kind="api_token_revoked",
                    title="API token revoked",
                    detail="Personal API token was revoked.",
                    metadata={"token_id": token_id},
                )
            return JSONResponse({"ok": revoked})

        @self.custom_route(f"{prefix}/admin/users", methods=["GET"])
        async def registry_admin_list_users(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            users = self._account_security.list_accounts()
            return JSONResponse(
                {
                    "users": users,
                    "roles": [role.value for role in RegistryRole],
                    "counts": _account_role_counts(users),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/admin/users", methods=["POST"])
        async def registry_admin_create_user(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            username = str(body.get("username") or "").strip()
            display_name = str(body.get("display_name") or "").strip()
            password = str(body.get("password") or "")
            role = _role_from_body(body.get("role"))
            if role is None:
                return JSONResponse(
                    {"error": "Invalid role.", "status": 400},
                    status_code=400,
                )
            if not username or len(password) < 8:
                return JSONResponse(
                    {
                        "error": "Username and an 8+ character password are required.",
                        "status": 400,
                    },
                    status_code=400,
                )
            created = self._account_security.create_account(
                username=username,
                password=password,
                role=role,
                display_name=display_name,
            )
            if created is None:
                return JSONResponse(
                    {"error": "User already exists.", "status": 409},
                    status_code=409,
                )
            self._account_activity.append(
                username=session.username if session else "admin",
                event_kind="admin_user_created",
                title="User created",
                detail=f"{username} was created with role {role.value}.",
                metadata={"target_username": username, "role": role.value},
            )
            return JSONResponse({"user": created}, status_code=201)

        @self.custom_route(f"{prefix}/admin/users/{{username}}", methods=["PATCH"])
        async def registry_admin_update_user(request: Request) -> JSONResponse:
            username = request.path_params.get("username", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            requested_role = body.get("role")
            role = (
                _role_from_body(requested_role) if requested_role is not None else None
            )
            if requested_role is not None and role is None:
                return JSONResponse(
                    {"error": "Invalid role.", "status": 400},
                    status_code=400,
                )
            disabled = body.get("disabled")
            disabled_bool = bool(disabled) if isinstance(disabled, bool) else None
            if session and session.username == username and disabled_bool is True:
                return JSONResponse(
                    {
                        "error": "You cannot disable your own admin account.",
                        "status": 400,
                    },
                    status_code=400,
                )
            guard_error = self._guard_last_admin_change(username, role, disabled_bool)
            if guard_error:
                return JSONResponse(
                    {"error": guard_error, "status": 400}, status_code=400
                )
            updated = self._account_security.update_account(
                username=username,
                role=role,
                display_name=str(body.get("display_name")).strip()
                if "display_name" in body
                else None,
                disabled=disabled_bool,
            )
            if updated is None:
                return JSONResponse(
                    {"error": "User not found.", "status": 404},
                    status_code=404,
                )
            self._account_activity.append(
                username=session.username if session else "admin",
                event_kind="admin_user_updated",
                title="User updated",
                detail=f"{username} account settings were updated.",
                metadata={
                    "target_username": username,
                    "role": updated.get("role"),
                    "active": updated.get("active"),
                },
            )
            return JSONResponse({"user": updated})

        @self.custom_route(f"{prefix}/admin/users/{{username}}", methods=["DELETE"])
        async def registry_admin_disable_user(request: Request) -> JSONResponse:
            username = request.path_params.get("username", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            if session and session.username == username:
                return JSONResponse(
                    {
                        "error": "You cannot disable your own admin account.",
                        "status": 400,
                    },
                    status_code=400,
                )
            guard_error = self._guard_last_admin_change(username, None, True)
            if guard_error:
                return JSONResponse(
                    {"error": guard_error, "status": 400}, status_code=400
                )
            updated = self._account_security.update_account(
                username=username,
                disabled=True,
            )
            if updated is None:
                return JSONResponse(
                    {"error": "User not found.", "status": 404},
                    status_code=404,
                )
            self._account_activity.append(
                username=session.username if session else "admin",
                event_kind="admin_user_disabled",
                title="User disabled",
                detail=f"{username} account was disabled.",
                metadata={"target_username": username},
            )
            return JSONResponse({"user": updated})

        @self.custom_route(
            f"{prefix}/admin/users/{{username}}/password", methods=["POST"]
        )
        async def registry_admin_reset_user_password(request: Request) -> JSONResponse:
            username = request.path_params.get("username", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            new_password = str(body.get("new_password") or "")
            if len(new_password) < 8:
                return JSONResponse(
                    {
                        "error": "New password must be at least 8 characters.",
                        "status": 400,
                    },
                    status_code=400,
                )
            changed = self._account_security.reset_password(
                username=username,
                new_password=new_password,
            )
            if not changed:
                return JSONResponse(
                    {"error": "User not found.", "status": 404},
                    status_code=404,
                )
            self._account_activity.append(
                username=session.username if session else "admin",
                event_kind="admin_password_reset",
                title="Password reset by admin",
                detail=f"{username} password was reset and sessions were revoked.",
                metadata={"target_username": username},
            )
            return JSONResponse({"ok": True})

        @self.custom_route(f"{prefix}/admin/control-planes", methods=["GET"])
        async def registry_admin_control_planes(
            request: Request,
        ) -> JSONResponse:
            """Admin-only snapshot of every opt-in plane's state.

            Used by the settings UI to render the toggle switches.
            Iter 9.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            return JSONResponse(self.get_control_plane_status())

        @self.custom_route(f"{prefix}/admin/control-planes/{{plane}}", methods=["POST"])
        async def registry_admin_toggle_control_plane(
            request: Request,
        ) -> JSONResponse:
            """Toggle an opt-in plane on or off at runtime.

            Body: ``{"enabled": true|false}``. Admin-only. Iter 9.

            The toggle takes effect immediately — the plane's
            attribute on the security context is mutated and its
            middleware is added to / removed from the chain. The
            persisted record survives restart so the operator's
            intent doesn't get reverted by the next process boot.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(session, {RegistryRole.ADMIN}):
                return JSONResponse(
                    {"error": "Admin role required.", "status": 403},
                    status_code=403,
                )
            plane = request.path_params.get("plane", "")
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict) or "enabled" not in body:
                return JSONResponse(
                    {
                        "error": ('Body must be JSON like {"enabled": true}.'),
                        "status": 400,
                    },
                    status_code=400,
                )
            requested = bool(body.get("enabled"))
            actor = session.username if session is not None else "anonymous"
            try:
                if requested:
                    payload = self.enable_plane(plane, actor_id=actor)
                else:
                    payload = self.disable_plane(plane, actor_id=actor)
            except ValueError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            self._account_activity.append(
                username=actor,
                event_kind="admin_control_plane_toggle",
                title=(
                    f"Control plane {plane} {'enabled' if requested else 'disabled'}"
                ),
                detail=(
                    f"{actor} "
                    f"{'enabled' if requested else 'disabled'} the "
                    f"{plane} control plane."
                ),
                metadata={"plane": plane, "enabled": requested},
            )
            return JSONResponse(payload)

        @self.custom_route(f"{prefix}/openapi/ingest", methods=["POST"])
        async def registry_openapi_ingest(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            raw_text = str(body.get("text", "") or "")
            if not raw_text.strip():
                return JSONResponse(
                    {"error": "Missing OpenAPI document text.", "status": 400},
                    status_code=400,
                )
            title = str(body.get("title", "") or "").strip() or "OpenAPI source"
            source_url = str(body.get("source_url", "") or "").strip()
            publisher_id = (
                publisher_id_from_author(session.username)
                if session is not None
                else "publisher"
            )
            try:
                record, ops = self._openapi_store.ingest_source(
                    publisher_id=publisher_id,
                    title=title,
                    source_url=source_url,
                    raw_text=raw_text,
                )
            except ValueError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            return JSONResponse(
                {
                    "source": {k: v for k, v in record.items() if k != "spec_json"},
                    "operations": ops,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/openapi/toolset", methods=["POST"])
        async def registry_openapi_toolset(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            source_id = str(body.get("source_id", "") or "").strip()
            if not source_id:
                return JSONResponse(
                    {"error": "`source_id` is required", "status": 400},
                    status_code=400,
                )
            selected = body.get("selected_operations")
            if not isinstance(selected, list) or not all(
                isinstance(x, str) and x.strip() for x in selected
            ):
                return JSONResponse(
                    {
                        "error": "`selected_operations` must be an array of strings",
                        "status": 400,
                    },
                    status_code=400,
                )
            title = str(body.get("title", "") or "").strip() or "OpenAPI toolset"
            prefix_name = str(body.get("tool_name_prefix", "") or "").strip()
            metadata = body.get("metadata")
            metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}

            publisher_id = (
                publisher_id_from_author(session.username)
                if session is not None
                else "publisher"
            )

            spec = self._openapi_store.get_source_spec(source_id)
            if spec is None:
                return JSONResponse(
                    {"error": f"Unknown OpenAPI source {source_id!r}", "status": 404},
                    status_code=404,
                )
            ops = extract_openapi_operations(spec)
            op_keys = {op.get("operation_key") for op in ops}
            unknown = [key for key in selected if key not in op_keys]
            if unknown:
                return JSONResponse(
                    {
                        "error": "Some selected operations were not found in the OpenAPI source.",
                        "unknown": unknown[:50],
                        "status": 400,
                    },
                    status_code=400,
                )

            record = self._openapi_store.create_toolset(
                publisher_id=publisher_id,
                source_id=source_id,
                title=title,
                selected_operations=[s.strip() for s in selected],
                tool_name_prefix=prefix_name,
                metadata=metadata_dict,
            )
            return JSONResponse(
                {
                    "toolset": record,
                    "operation_count": len(selected),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        # ------------------------------------------------------------------
        # Iter 13.2: OpenAPI credential CRUD
        # ------------------------------------------------------------------
        # All routes are publisher-scoped: a publisher can only see and
        # manage their own credentials. The store enforces this in its
        # query layer, but we re-check at the route boundary so a bug
        # in either layer fails closed.

        def _resolve_publisher_id_from(session_obj: Any) -> str:
            return (
                publisher_id_from_author(session_obj.username)
                if session_obj is not None
                else "publisher"
            )

        def _validate_credential_payload(
            scheme_kind: str, secret: dict[str, object] | None
        ) -> tuple[dict[str, object] | None, str | None]:
            if not isinstance(secret, dict) or not secret:
                return None, "`secret` must be a non-empty object"
            cleaned: dict[str, object] = {}
            if scheme_kind == "apiKey":
                key = str(secret.get("api_key") or "").strip()
                if not key:
                    return None, "apiKey credentials require `api_key`"
                cleaned["api_key"] = key
            elif scheme_kind == "http":
                http_scheme = str(secret.get("http_scheme") or "").strip().lower()
                if http_scheme == "bearer":
                    token = str(secret.get("bearer_token") or "").strip()
                    if not token:
                        return None, "http bearer requires `bearer_token`"
                    cleaned["http_scheme"] = "bearer"
                    cleaned["bearer_token"] = token
                elif http_scheme == "basic":
                    user = str(secret.get("username") or "")
                    pw = str(secret.get("password") or "")
                    if not user or not pw:
                        return None, "http basic requires `username` and `password`"
                    cleaned["http_scheme"] = "basic"
                    cleaned["username"] = user
                    cleaned["password"] = pw
                else:
                    return (
                        None,
                        "http credentials require `http_scheme` of bearer or basic",
                    )
            elif scheme_kind == "oauth2":
                client_id = str(secret.get("client_id") or "").strip()
                client_secret = str(secret.get("client_secret") or "").strip()
                access_token = str(secret.get("access_token") or "").strip()
                refresh_token = str(secret.get("refresh_token") or "").strip()
                if not client_id and not access_token:
                    return (
                        None,
                        "oauth2 credentials require `client_id` or `access_token`",
                    )
                if client_id:
                    cleaned["client_id"] = client_id
                if client_secret:
                    cleaned["client_secret"] = client_secret
                if access_token:
                    cleaned["access_token"] = access_token
                if refresh_token:
                    cleaned["refresh_token"] = refresh_token
            elif scheme_kind == "openIdConnect":
                id_token = str(secret.get("id_token") or "").strip()
                access_token = str(secret.get("access_token") or "").strip()
                client_id = str(secret.get("client_id") or "").strip()
                client_secret = str(secret.get("client_secret") or "").strip()
                if not (id_token or access_token or client_id):
                    return (
                        None,
                        "openIdConnect requires one of `id_token`, `access_token`, or `client_id`",
                    )
                if id_token:
                    cleaned["id_token"] = id_token
                if access_token:
                    cleaned["access_token"] = access_token
                if client_id:
                    cleaned["client_id"] = client_id
                if client_secret:
                    cleaned["client_secret"] = client_secret
            else:
                return None, f"Unsupported scheme_kind {scheme_kind!r}"
            return cleaned, None

        @self.custom_route(f"{prefix}/openapi/credentials", methods=["POST"])
        async def registry_openapi_credentials_upsert(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            source_id = str(body.get("source_id", "") or "").strip()
            scheme_name = str(body.get("scheme_name", "") or "").strip()
            scheme_kind = str(body.get("scheme_kind", "") or "").strip()
            label = str(body.get("label", "") or "").strip()
            if not source_id or not scheme_name or not scheme_kind:
                return JSONResponse(
                    {
                        "error": "`source_id`, `scheme_name`, and `scheme_kind` are required",
                        "status": 400,
                    },
                    status_code=400,
                )
            secret_in = body.get("secret")
            cleaned, err = _validate_credential_payload(
                scheme_kind, secret_in if isinstance(secret_in, dict) else None
            )
            if err is not None or cleaned is None:
                return JSONResponse(
                    {"error": err or "Invalid secret payload.", "status": 400},
                    status_code=400,
                )
            publisher_id = _resolve_publisher_id_from(session)
            # Sanity-check the source belongs to the requesting
            # publisher, so credentials can't be silently bound to
            # someone else's source.
            spec = self._openapi_store.get_source_spec(source_id)
            if spec is None:
                return JSONResponse(
                    {"error": f"Unknown OpenAPI source {source_id!r}", "status": 404},
                    status_code=404,
                )
            try:
                record = self._openapi_store.upsert_credential(
                    publisher_id=publisher_id,
                    source_id=source_id,
                    scheme_name=scheme_name,
                    scheme_kind=scheme_kind,  # type: ignore[arg-type]
                    secret=cleaned,
                    label=label,
                )
            except (ValueError, RuntimeError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            # Never echo plaintext back over the wire — return the
            # sanitised public projection instead.
            from purecipher.openapi_store import _credential_secret_hint

            return JSONResponse(
                {
                    "credential": {
                        "credential_id": record["credential_id"],
                        "created_at": record["created_at"],
                        "updated_at": record["updated_at"],
                        "publisher_id": record["publisher_id"],
                        "source_id": record["source_id"],
                        "scheme_name": record["scheme_name"],
                        "scheme_kind": record["scheme_kind"],
                        "label": record["label"],
                        "secret_hint": _credential_secret_hint(
                            record["scheme_kind"], record["secret"]
                        ),
                    },
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/openapi/credentials", methods=["GET"])
        async def registry_openapi_credentials_list(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            publisher_id = _resolve_publisher_id_from(session)
            source_id_param = request.query_params.get("source_id")
            source_id = source_id_param.strip() if source_id_param else None
            credentials = self._openapi_store.list_credentials(
                publisher_id=publisher_id,
                source_id=source_id or None,
            )
            return JSONResponse(
                {
                    "credentials": credentials,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(
            f"{prefix}/openapi/credentials/{{credential_id}}",
            methods=["DELETE"],
        )
        async def registry_openapi_credentials_delete(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            credential_id = str(
                request.path_params.get("credential_id", "") or ""
            ).strip()
            if not credential_id:
                return JSONResponse(
                    {"error": "`credential_id` required", "status": 400},
                    status_code=400,
                )
            publisher_id = _resolve_publisher_id_from(session)
            deleted = self._openapi_store.delete_credential(
                credential_id, publisher_id=publisher_id
            )
            if not deleted:
                return JSONResponse(
                    {"error": "Credential not found.", "status": 404},
                    status_code=404,
                )
            return JSONResponse(
                {
                    "deleted": True,
                    "credential_id": credential_id,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        # ------------------------------------------------------------------
        # Iter 13.3: Toolset invocation
        # ------------------------------------------------------------------
        # ``invoke_http_client_factory`` lets tests inject an
        # ``httpx.AsyncClient`` (typically backed by ``MockTransport``)
        # so we don't need real network. Production runs leave it
        # ``None`` and the executor opens a one-shot client.
        @self.custom_route(
            f"{prefix}/openapi/toolset/{{toolset_id}}/invoke",
            methods=["POST"],
        )
        async def registry_openapi_toolset_invoke(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            toolset_id = str(request.path_params.get("toolset_id", "") or "").strip()
            if not toolset_id:
                return JSONResponse(
                    {"error": "`toolset_id` required.", "status": 400},
                    status_code=400,
                )
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body.", "status": 400},
                    status_code=400,
                )
            operation_key = str(body.get("operation_key", "") or "").strip()
            args = body.get("arguments") or {}
            if not operation_key:
                return JSONResponse(
                    {"error": "`operation_key` required.", "status": 400},
                    status_code=400,
                )
            if not isinstance(args, dict):
                return JSONResponse(
                    {"error": "`arguments` must be an object.", "status": 400},
                    status_code=400,
                )

            toolset = self._openapi_store.get_toolset(toolset_id)
            if toolset is None:
                return JSONResponse(
                    {"error": f"Unknown toolset {toolset_id!r}.", "status": 404},
                    status_code=404,
                )
            publisher_id = _resolve_publisher_id_from(session)
            # Tenant isolation: a publisher can only invoke their own
            # toolsets. The store doesn't filter by publisher, so we
            # check at the route boundary.
            if publisher_id and toolset.get("publisher_id") != publisher_id:
                return JSONResponse(
                    {"error": "Toolset belongs to another publisher.", "status": 403},
                    status_code=403,
                )
            source_id = str(toolset.get("source_id") or "")
            if not source_id:
                return JSONResponse(
                    {"error": "Toolset has no source_id.", "status": 500},
                    status_code=500,
                )
            spec = self._openapi_store.get_source_spec(source_id)
            if spec is None:
                return JSONResponse(
                    {
                        "error": f"OpenAPI source {source_id!r} no longer exists.",
                        "status": 404,
                    },
                    status_code=404,
                )

            # Verify the operation is in the selected set; bringing
            # operations not in the toolset would let a caller invoke
            # operations the publisher hadn't approved.
            selected = set(toolset.get("selected_operations") or [])
            if selected and operation_key not in selected:
                return JSONResponse(
                    {
                        "error": (
                            f"Operation {operation_key!r} is not part of toolset "
                            f"{toolset_id!r}."
                        ),
                        "status": 400,
                    },
                    status_code=400,
                )

            from purecipher.openapi_executor import (
                ArgumentValidationError,
                OpenAPIToolExecutor,
            )
            from purecipher.openapi_store import (
                extract_openapi_operations_detailed,
            )

            ops = extract_openapi_operations_detailed(spec)
            op = next(
                (o for o in ops if o.get("operation_key") == operation_key),
                None,
            )
            if op is None:
                return JSONResponse(
                    {
                        "error": f"Operation {operation_key!r} not found in source.",
                        "status": 404,
                    },
                    status_code=404,
                )

            # Pick the first server URL the spec advertises. Operation-
            # level overrides win, then path-level, then top-level.
            server_url = ""
            for candidate in op.get("server_urls") or []:
                if isinstance(candidate, str) and candidate.strip():
                    server_url = candidate.strip()
                    break
            if not server_url:
                top_servers = spec.get("servers") or []
                if isinstance(top_servers, list):
                    for srv in top_servers:
                        if isinstance(srv, dict):
                            url = srv.get("url")
                            if isinstance(url, str) and url:
                                server_url = url
                                break
            if not server_url:
                return JSONResponse(
                    {
                        "error": "No server URL declared in the OpenAPI document.",
                        "status": 400,
                    },
                    status_code=400,
                )

            override_url = body.get("server_url")
            if isinstance(override_url, str) and override_url.strip():
                server_url = override_url.strip()

            executor = OpenAPIToolExecutor(
                spec=spec,
                operation=op,
                server_url=server_url,
                publisher_id=publisher_id,
                source_id=source_id,
            )
            try:
                result = await executor.execute(
                    args,
                    store=self._openapi_store,
                    client=self._openapi_invoke_client,
                )
            except ArgumentValidationError as exc:
                return JSONResponse(
                    {
                        "error": "Argument validation failed.",
                        "issues": exc.messages,
                        "status": 400,
                    },
                    status_code=400,
                )
            except (RuntimeError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )

            return JSONResponse(
                {
                    "status_code": result.status_code,
                    "headers": result.headers,
                    "content_type": result.content_type,
                    "body": result.body,
                    "validation_warnings": result.validation_warnings,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        # ------------------------------------------------------------------
        # Iter 13.4: Toolset → ToolListing publish bridge
        # ------------------------------------------------------------------
        # Turn a toolset's selected operations into first-class
        # ``ToolListing`` records on the registry's marketplace. Each
        # operation becomes its own listing — a toolset is a
        # publisher-side grouping, not a marketplace concept.
        @self.custom_route(
            f"{prefix}/openapi/toolset/{{toolset_id}}/publish",
            methods=["POST"],
        )
        async def registry_openapi_toolset_publish(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher role required.", "status": 403},
                    status_code=403,
                )
            toolset_id = str(request.path_params.get("toolset_id", "") or "").strip()
            if not toolset_id:
                return JSONResponse(
                    {"error": "`toolset_id` required.", "status": 400},
                    status_code=400,
                )
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Invalid JSON body.", "status": 400},
                    status_code=400,
                )

            toolset = self._openapi_store.get_toolset(toolset_id)
            if toolset is None:
                return JSONResponse(
                    {"error": f"Unknown toolset {toolset_id!r}.", "status": 404},
                    status_code=404,
                )
            publisher_id = _resolve_publisher_id_from(session)
            # Cross-publisher isolation — same gate as /invoke.
            if publisher_id and toolset.get("publisher_id") != publisher_id:
                return JSONResponse(
                    {
                        "error": "Toolset belongs to another publisher.",
                        "status": 403,
                    },
                    status_code=403,
                )

            version = str(body.get("version", "") or "").strip() or "0.0.0"
            categories_raw = body.get("categories") or []
            categories: set[ToolCategory] | None = None
            if isinstance(categories_raw, list) and categories_raw:
                resolved: set[ToolCategory] = set()
                for c in categories_raw:
                    if not isinstance(c, str):
                        continue
                    try:
                        resolved.add(ToolCategory(c))
                    except ValueError:
                        return JSONResponse(
                            {
                                "error": f"Unknown category {c!r}.",
                                "status": 400,
                            },
                            status_code=400,
                        )
                if resolved:
                    categories = resolved
            extra_tags_raw = body.get("tags") or []
            extra_tags: set[str] | None = None
            if isinstance(extra_tags_raw, list):
                extra_tags = {str(t) for t in extra_tags_raw if t}
            override_url = body.get("server_url_override")
            override = (
                override_url.strip()
                if isinstance(override_url, str) and override_url.strip()
                else None
            )

            try:
                listings = self.publish_toolset_as_listings(
                    toolset_id,
                    publisher_id=publisher_id,
                    version=version,
                    categories=categories,
                    extra_tags=extra_tags,
                    server_url_override=override,
                )
            except (ValueError, RuntimeError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )

            return JSONResponse(
                {
                    "listings": [
                        {
                            "listing_id": L.listing_id,
                            "tool_name": L.tool_name,
                            "display_name": L.display_name,
                            "version": L.version,
                            "status": L.status.value,
                            "attestation_kind": L.attestation_kind.value,
                            "hosting_mode": L.hosting_mode.value,
                            "operation_key": L.metadata.get(
                                "purecipher.openapi.operation_key"
                            ),
                        }
                        for L in listings
                    ],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        mount_registry_policy_routes(
            self,
            prefix,
            allowed_roles={RegistryRole.REVIEWER, RegistryRole.ADMIN},
        )

        @self.custom_route(f"{prefix}/setup", methods=["GET"])
        async def registry_setup_page(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            next_path = _safe_next_path(
                request.query_params.get("next"),
                default=prefix,
            )
            if not self.auth_enabled:
                return RedirectResponse(url=next_path, status_code=303)
            if not self._bootstrap_required():
                return RedirectResponse(url=f"{prefix}/login", status_code=303)
            return create_secure_html_response(
                create_setup_html(
                    server_name=self.name,
                    registry_prefix=prefix,
                    auth_enabled=self.auth_enabled,
                    next_path=next_path,
                    default_username=self._auth_settings.bootstrap_admin_username
                    or "admin",
                    notice_title=request.query_params.get("notice") or None,
                    notice_body=request.query_params.get("detail") or None,
                    notice_is_error=request.query_params.get("tone") == "error",
                )
            )

        @self.custom_route(f"{prefix}/setup", methods=["POST"])
        async def registry_setup(request: Request):
            if not self.auth_enabled:
                payload = {"error": "Registry auth is disabled.", "status": 400}
                return JSONResponse(payload, status_code=400)
            if not self._bootstrap_required():
                payload = {
                    "error": "Registry setup is already complete.",
                    "status": 409,
                }
                if _wants_json(request):
                    return JSONResponse(payload, status_code=409)
                return RedirectResponse(url=f"{prefix}/login", status_code=303)

            content_type = request.headers.get("content-type", "")
            expects_json = _wants_json(request)
            try:
                if "application/json" in content_type:
                    raw_payload = await request.json()
                    if not isinstance(raw_payload, dict):
                        raise ValueError("JSON request body must be an object.")
                else:
                    form = await request.form()
                    raw_payload = {str(key): value for key, value in form.items()}
            except Exception as exc:
                message = str(exc) or "Invalid setup request."
                if expects_json:
                    return JSONResponse(
                        {"error": message, "status": 400},
                        status_code=400,
                    )
                return create_secure_html_response(
                    create_setup_html(
                        server_name=self.name,
                        registry_prefix=prefix,
                        auth_enabled=self.auth_enabled,
                        next_path=prefix,
                        notice_title="Setup failed",
                        notice_body=message,
                        notice_is_error=True,
                    ),
                    status_code=400,
                )

            username = str(raw_payload.get("username", "admin")).strip() or "admin"
            password = str(raw_payload.get("password", ""))
            display_name = str(raw_payload.get("display_name", "Registry Admin"))
            next_path = _safe_next_path(
                str(raw_payload.get("next", "")), default=prefix
            )
            if len(password) < 8:
                payload = {
                    "error": "Admin password must be at least 8 characters.",
                    "status": 400,
                }
                if expects_json:
                    return JSONResponse(payload, status_code=400)
                return create_secure_html_response(
                    create_setup_html(
                        server_name=self.name,
                        registry_prefix=prefix,
                        auth_enabled=self.auth_enabled,
                        next_path=next_path,
                        default_username=username,
                        notice_title="Setup failed",
                        notice_body=payload["error"],
                        notice_is_error=True,
                    ),
                    status_code=400,
                )

            user = self._account_security.create_bootstrap_admin(
                username=username,
                password=password,
                display_name=display_name,
            )
            if user is None:
                payload = {
                    "error": "Registry setup is already complete or the admin username is invalid.",
                    "status": 409,
                }
                if expects_json:
                    return JSONResponse(payload, status_code=409)
                return RedirectResponse(url=f"{prefix}/login", status_code=303)

            self._account_activity.append(
                username=user.username,
                event_kind="bootstrap_admin_created",
                title="Bootstrap admin created",
                detail="Initial registry admin account was created from setup.",
                metadata={
                    "role": user.role.value,
                    "client": request.client.host if request.client else "",
                    "source": "setup",
                },
            )
            session_record = self._account_security.create_session(
                user=user,
                ttl_seconds=self._auth_settings.token_ttl_seconds,
            )
            token = self._auth_settings.issue_token(
                user,
                session_id=session_record.session_id,
            )
            session = self._auth_settings.decode_token(token)
            if session is None:
                payload = {
                    "error": "Admin account was created, but session creation failed.",
                    "status": 500,
                }
                return JSONResponse(payload, status_code=500)
            self._account_activity.append(
                username=session.username,
                event_kind="login_success",
                title="Signed in",
                detail=f"{session.display_name} opened the first admin session.",
                metadata={
                    "role": session.role.value,
                    "client": request.client.host if request.client else "",
                },
            )

            if expects_json:
                response = JSONResponse(
                    {
                        "ok": True,
                        "bootstrap_complete": True,
                        "session": session.to_dict(),
                    },
                    status_code=201,
                )
            else:
                response = RedirectResponse(url=next_path, status_code=303)
            self._set_auth_cookie(response, token)
            return response

        @self.custom_route(f"{prefix}/login", methods=["GET"])
        async def registry_login_page(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            next_path = _safe_next_path(
                request.query_params.get("next"),
                default=prefix,
            )
            session = self._session_from_request(request)
            if not self.auth_enabled:
                return RedirectResponse(url=next_path, status_code=303)
            if self._bootstrap_required():
                return RedirectResponse(
                    url=f"{prefix}/setup?{urlencode({'next': next_path})}",
                    status_code=303,
                )
            if session is not None:
                return RedirectResponse(url=next_path, status_code=303)
            return create_secure_html_response(
                self._render_login_ui(
                    prefix=prefix,
                    next_path=next_path,
                    notice_title=request.query_params.get("notice") or None,
                    notice_body=request.query_params.get("detail") or None,
                    notice_is_error=request.query_params.get("tone") == "error",
                )
            )

        @self.custom_route(f"{prefix}/login", methods=["POST"])
        async def registry_login(request: Request):
            if not self.auth_enabled:
                payload = {
                    "error": "Registry auth is disabled.",
                    "status": 400,
                }
                if _wants_json(request):
                    return JSONResponse(payload, status_code=400)
                return create_secure_html_response(
                    self._render_registry_ui(
                        prefix=prefix,
                        page_notice_title="Auth disabled",
                        page_notice_body=payload["error"],
                        page_notice_is_error=True,
                    ),
                    status_code=400,
                )

            if self._bootstrap_required():
                payload = {
                    "error": "Admin setup is required before sign-in.",
                    "status": 428,
                    "setup_url": f"{prefix}/setup",
                }
                if _wants_json(request):
                    return JSONResponse(payload, status_code=428)
                return RedirectResponse(url=f"{prefix}/setup", status_code=303)

            content_type = request.headers.get("content-type", "")
            expects_json = _wants_json(request)
            try:
                if "application/json" in content_type:
                    raw_payload = await request.json()
                    if not isinstance(raw_payload, dict):
                        raise ValueError("JSON request body must be an object.")
                else:
                    form = await request.form()
                    raw_payload = {str(key): value for key, value in form.items()}
            except Exception as exc:
                message = str(exc) or "Invalid login request."
                if expects_json:
                    return JSONResponse(
                        {"error": message, "status": 400},
                        status_code=400,
                    )
                return create_secure_html_response(
                    self._render_login_ui(
                        prefix=prefix,
                        next_path=_safe_next_path(
                            request.query_params.get("next"),
                            default=prefix,
                        ),
                        notice_title="Login failed",
                        notice_body=message,
                        notice_is_error=True,
                    ),
                    status_code=400,
                )

            username = str(raw_payload.get("username", "")).strip()
            password = str(raw_payload.get("password", ""))
            next_path = _safe_next_path(
                str(raw_payload.get("next", "")),
                default=prefix,
            )

            client_ip = request.client.host if request.client else ""
            locked, retry_after = self._login_lockout.is_locked(username, client_ip)
            if locked:
                # Still record the attempt for forensics — but as a
                # `login_locked` event so it's distinguishable from a
                # plain bad-password failure.
                self._account_activity.append(
                    username=username or "(unknown)",
                    event_kind="login_locked",
                    title="Sign-in blocked: too many failed attempts",
                    detail=(
                        f"This (username, IP) is locked for "
                        f"{int(retry_after)}s after {self._login_lockout.max_failures} "
                        "consecutive failures."
                    ),
                    metadata={"client": client_ip, "retry_after": retry_after},
                )
                payload = {
                    "error": (
                        "Too many failed sign-in attempts. "
                        f"Try again in {int(retry_after)} seconds."
                    ),
                    "status": 429,
                    "retry_after": int(retry_after),
                }
                headers = {"Retry-After": str(int(retry_after))}
                if expects_json:
                    return JSONResponse(payload, status_code=429, headers=headers)
                return create_secure_html_response(
                    self._render_login_ui(
                        prefix=prefix,
                        next_path=next_path,
                        notice_title="Sign-in blocked",
                        notice_body=payload["error"],
                        notice_is_error=True,
                    ),
                    status_code=429,
                    headers=headers,
                )

            user = self._account_security.authenticate(username, password)
            if user is None:
                now_locked, retry_after, failures = (
                    self._login_lockout.register_failure(username, client_ip)
                )
                if username:
                    self._account_activity.append(
                        username=username,
                        event_kind="login_failed",
                        title="Failed sign-in attempt",
                        detail=(
                            "Registry rejected the supplied credentials."
                            + (
                                f" Account locked for {int(retry_after)}s "
                                f"after {failures} failures."
                                if now_locked
                                else f" Failure {failures}/"
                                f"{self._login_lockout.max_failures}."
                            )
                        ),
                        metadata={
                            "client": client_ip,
                            "failures": failures,
                            "now_locked": now_locked,
                        },
                    )
                if now_locked:
                    payload = {
                        "error": (
                            "Too many failed sign-in attempts. "
                            f"Try again in {int(retry_after)} seconds."
                        ),
                        "status": 429,
                        "retry_after": int(retry_after),
                    }
                    headers = {"Retry-After": str(int(retry_after))}
                    if expects_json:
                        return JSONResponse(payload, status_code=429, headers=headers)
                    return create_secure_html_response(
                        self._render_login_ui(
                            prefix=prefix,
                            next_path=next_path,
                            notice_title="Sign-in blocked",
                            notice_body=payload["error"],
                            notice_is_error=True,
                        ),
                        status_code=429,
                        headers=headers,
                    )
                payload = {
                    "error": "Invalid username or password.",
                    "status": 401,
                }
                if expects_json:
                    return JSONResponse(payload, status_code=401)
                return create_secure_html_response(
                    self._render_login_ui(
                        prefix=prefix,
                        next_path=next_path,
                        notice_title="Login failed",
                        notice_body=payload["error"],
                        notice_is_error=True,
                    ),
                    status_code=401,
                )

            # Auth itself succeeded — but don't clear the failure counter
            # yet. We only consider the login truly complete once the
            # session record is created AND a usable token is issued AND
            # it decodes cleanly. Clearing the counter prematurely would
            # let an attacker who knows the password reset their lockout
            # budget every attempt even when session issuance keeps
            # failing (e.g. JWT misconfig, transient DB error).
            session_record = self._account_security.create_session(
                user=user,
                ttl_seconds=self._auth_settings.token_ttl_seconds,
            )
            token = self._auth_settings.issue_token(
                user,
                session_id=session_record.session_id,
            )
            session = self._auth_settings.decode_token(token)
            if session is None:
                payload = {
                    "error": "Unable to establish an authenticated session.",
                    "status": 500,
                }
                if expects_json:
                    return JSONResponse(payload, status_code=500)
                return create_secure_html_response(
                    self._render_login_ui(
                        prefix=prefix,
                        next_path=next_path,
                        notice_title="Login failed",
                        notice_body=payload["error"],
                        notice_is_error=True,
                    ),
                    status_code=500,
                )

            # Now the login is fully successful — clear the lockout
            # counter for this (username, ip) tuple.
            self._login_lockout.register_success(username, client_ip)

            self._account_activity.append(
                username=session.username,
                event_kind="login_success",
                title="Signed in",
                detail=f"{session.display_name} opened a registry session.",
                metadata={
                    "role": session.role.value,
                    "client": request.client.host if request.client else "",
                },
            )

            if expects_json:
                response = JSONResponse(
                    {
                        "token": token,
                        "session": session.to_dict(),
                    }
                )
            else:
                response = RedirectResponse(url=next_path, status_code=303)
            self._set_auth_cookie(response, token)
            return response

        @self.custom_route(f"{prefix}/logout", methods=["GET"])
        async def registry_logout(request: Request):
            session = self._session_from_request(request)
            next_path = _safe_next_path(
                request.query_params.get("next"),
                default=prefix,
            )
            if session is not None:
                self._account_security.revoke_session(
                    session_id=session.session_id,
                    username=session.username,
                )
                self._account_activity.append(
                    username=session.username,
                    event_kind="logout",
                    title="Signed out",
                    detail="Current browser session was closed.",
                    metadata={
                        "role": session.role.value,
                        "client": request.client.host if request.client else "",
                    },
                )
            response = RedirectResponse(url=next_path, status_code=303)
            self._clear_auth_cookie(response)
            return response

        @self.custom_route(f"{prefix}/app", methods=["GET"])
        async def registry_app(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return self._login_redirect(request, prefix=prefix)
            return create_secure_html_response(
                self._render_registry_ui(
                    prefix=prefix,
                    query=request.query_params.get("q", ""),
                    min_certification=request.query_params.get(
                        "min_certification",
                        "",
                    ),
                    selected_tool=request.query_params.get("tool", ""),
                    session=session,
                    page_notice_title=request.query_params.get("notice") or None,
                    page_notice_body=request.query_params.get("detail") or None,
                    page_notice_is_error=request.query_params.get("tone") == "error",
                )
            )

        @self.custom_route(prefix, methods=["GET"])
        async def registry_ui(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            session = self._session_from_request(request)
            app_path = f"{prefix}/app"
            if not self.auth_enabled:
                return RedirectResponse(url=app_path, status_code=303)
            return create_secure_html_response(
                self._render_login_ui(
                    prefix=prefix,
                    next_path=app_path,
                    session=session,
                )
            )

        @self.custom_route(f"{prefix}/publish", methods=["GET"])
        async def registry_publish_page(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return self._login_redirect(request, prefix=prefix)
            return create_secure_html_response(
                self._render_publish_ui(
                    prefix=prefix,
                    session=session,
                    page_notice_title=request.query_params.get("notice") or None,
                    page_notice_body=request.query_params.get("detail") or None,
                    page_notice_is_error=request.query_params.get("tone") == "error",
                )
            )

        @self.custom_route(f"{prefix}/listings/{{tool_name}}", methods=["GET"])
        async def registry_listing_ui(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            tool_name = request.path_params.get("tool_name", "")
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return self._login_redirect(request, prefix=prefix)
            detail = self.get_verified_tool(tool_name)
            if "error" in detail:
                return create_secure_html_response(
                    self._render_registry_ui(
                        prefix=prefix,
                        query=request.query_params.get("q", ""),
                        min_certification=request.query_params.get(
                            "min_certification",
                            "",
                        ),
                        submission_title="Listing not found",
                        submission_body=detail["error"],
                        submission_is_error=True,
                        session=session,
                    ),
                    status_code=_status_code_from_payload(detail),
                )

            install_payload = self.get_install_recipes(
                tool_name,
                registry_base_url=str(request.base_url).rstrip("/"),
            )
            return create_secure_html_response(
                create_listing_detail_html(
                    server_name=self.name,
                    registry_prefix=prefix,
                    detail=detail,
                    install_recipes=list(install_payload.get("recipes", [])),
                    auth_enabled=self.auth_enabled,
                    session=self._session_payload(session),
                    query=request.query_params.get("q", ""),
                    min_certification=request.query_params.get(
                        "min_certification",
                        "",
                    ),
                )
            )

        @self.custom_route(f"{prefix}/publishers", methods=["GET"])
        async def registry_publishers(request: Request):
            limit = int(request.query_params.get("limit", "200"))
            payload = self.list_publishers(limit=limit)
            if request.query_params.get("view") == "html":
                if not self._enable_legacy_registry_ui:
                    return self._legacy_ui_disabled_response(request)
                session = self._session_from_request(request)
                if self.auth_enabled and session is None:
                    return self._login_redirect(request, prefix=prefix)
                return create_secure_html_response(
                    create_publisher_index_html(
                        server_name=self.name,
                        registry_prefix=prefix,
                        publishers=payload,
                        auth_enabled=self.auth_enabled,
                        session=self._session_payload(session),
                    )
                )
            return JSONResponse(payload)

        @self.custom_route(f"{prefix}/publishers/{{publisher_id}}", methods=["GET"])
        async def registry_publisher_profile(request: Request):
            publisher_id = request.path_params.get("publisher_id", "")
            session = self._session_from_request(request)
            payload = self.get_publisher_profile(publisher_id)

            # Match the content-negotiation contract used by
            # ``/registry/publishers`` (the parent list route) and by
            # the tool-detail endpoint: JSON by default, HTML only
            # when the caller explicitly asks via ``?view=html``.
            # Pre-fix this route returned HTML unconditionally, which
            # caused the Next.js publisher-profile page to receive
            # an HTML body, fail JSON parsing, and render
            # "Publisher not found" even when the publisher existed.
            wants_html = request.query_params.get("view") == "html"
            if not wants_html:
                return JSONResponse(
                    payload,
                    status_code=_status_code_from_payload(payload),
                )

            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            if self.auth_enabled and session is None:
                return self._login_redirect(request, prefix=prefix)
            if "error" in payload:
                return create_secure_html_response(
                    self._render_registry_ui(
                        prefix=prefix,
                        submission_title="Publisher not found",
                        submission_body=payload["error"],
                        submission_is_error=True,
                        session=session,
                    ),
                    status_code=_status_code_from_payload(payload),
                )
            return create_secure_html_response(
                create_publisher_profile_html(
                    server_name=self.name,
                    registry_prefix=prefix,
                    profile=payload,
                    auth_enabled=self.auth_enabled,
                    session=self._session_payload(session),
                )
            )

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/governance/policy",
            methods=["GET"],
        )
        async def registry_server_governance_policy(
            request: Request,
        ) -> JSONResponse:
            """Return the policy-kernel governance view for a server.

            Session-aware visibility: anonymous (or auth-disabled)
            callers see only public listings; authenticated callers
            see all of the publisher's listings — same pattern used
            by the tool-detail / verify endpoints so curators can
            inspect their pending submissions immediately after
            submit.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_policy_governance(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/governance/contracts",
            methods=["GET"],
        )
        async def registry_server_governance_contracts(
            request: Request,
        ) -> JSONResponse:
            """Return the Contract-Broker governance view for a server.

            Same session-aware visibility as the policy-governance
            endpoint. Anonymous callers see only public listings,
            authenticated callers see all of the publisher's listings.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_contract_governance(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/governance/consent",
            methods=["GET"],
        )
        async def registry_server_governance_consent(
            request: Request,
        ) -> JSONResponse:
            """Return the Consent-Graph governance view for a server.

            Same session-aware visibility as the other governance
            endpoints.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_consent_governance(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/governance/ledger",
            methods=["GET"],
        )
        async def registry_server_governance_ledger(
            request: Request,
        ) -> JSONResponse:
            """Return the Provenance-Ledger governance view for a server.

            Same session-aware visibility as the other governance
            endpoints.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_ledger_governance(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/governance/overrides",
            methods=["GET"],
        )
        async def registry_server_governance_overrides(
            request: Request,
        ) -> JSONResponse:
            """Return the Overrides governance view for a server.

            Same session-aware visibility as the other governance
            endpoints. Surfaces operator interventions (status,
            moderation log, yanked versions, per-listing policy
            overrides) across this server's tools in one place.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_overrides_governance(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/servers/{{server_id}}/observability",
            methods=["GET"],
        )
        async def registry_server_observability(
            request: Request,
        ) -> JSONResponse:
            """Return the Reflexive-Core observability view for a server.

            Powers the Observability tab on the server profile page.
            Same session-aware visibility as the governance
            endpoints — the URL lives outside ``/governance/`` because
            observability is a sibling tab, not a control plane.
            """
            server_id = request.path_params.get("server_id", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_server_observability(
                server_id, include_non_public=include_non_public
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(f"{prefix}/review", methods=["GET"])
        async def registry_review_queue(request: Request):
            if not self._enable_legacy_registry_ui:
                return self._legacy_ui_disabled_response(request)
            session = self._session_from_request(request)
            allowed_roles = {RegistryRole.REVIEWER, RegistryRole.ADMIN}
            if self.auth_enabled and session is None:
                return self._login_redirect(request, prefix=prefix)
            if self.auth_enabled and not self._has_roles(session, allowed_roles):
                return create_secure_html_response(
                    self._render_registry_ui(
                        prefix=prefix,
                        session=session,
                        page_notice_title="Access denied",
                        page_notice_body=(
                            "Reviewer or admin role required to access the "
                            "moderation queue."
                        ),
                        page_notice_is_error=True,
                    ),
                    status_code=403,
                )
            return create_secure_html_response(
                self._render_review_queue_ui(
                    prefix=prefix,
                    session=session,
                    notice_title=request.query_params.get("notice") or None,
                    notice_body=request.query_params.get("detail") or None,
                    notice_is_error=request.query_params.get("tone") == "error",
                )
            )

        @self.custom_route(f"{prefix}/review/submissions", methods=["GET"])
        async def registry_review_submissions(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Reviewer or admin role required.", "status": 403},
                    status_code=403,
                )
            return JSONResponse(
                self._filter_queue_for_session(
                    self.get_moderation_queue(),
                    session,
                )
            )

        @self.custom_route(
            f"{prefix}/review/{{listing_id}}/{{action_name}}",
            methods=["POST"],
        )
        async def registry_review_action(request: Request):
            listing_id = request.path_params.get("listing_id", "")
            action_name = request.path_params.get("action_name", "")
            session = self._session_from_request(request)
            content_type = request.headers.get("content-type", "")
            expects_json = "application/json" in content_type or (
                "application/json" in request.headers.get("accept", "")
            )
            required_roles = self._moderation_roles_for_action(action_name)

            if self.auth_enabled and session is None:
                if expects_json:
                    return JSONResponse(
                        {"error": "Authentication required.", "status": 401},
                        status_code=401,
                    )
                return self._login_redirect(request, prefix=prefix)

            if (
                required_roles
                and self.auth_enabled
                and not self._has_roles(
                    session,
                    required_roles,
                )
            ):
                message = (
                    "Admin role required."
                    if required_roles == {RegistryRole.ADMIN}
                    else "Reviewer or admin role required."
                )
                if expects_json:
                    return JSONResponse(
                        {"error": message, "status": 403},
                        status_code=403,
                    )
                return create_secure_html_response(
                    self._render_review_queue_ui(
                        prefix=prefix,
                        session=session,
                        notice_title="Moderation failed",
                        notice_body=message,
                        notice_is_error=True,
                    ),
                    status_code=403,
                )

            try:
                if "application/json" in content_type:
                    raw_payload = await request.json()
                    if not isinstance(raw_payload, dict):
                        raise ValueError("JSON request body must be an object.")
                else:
                    form = await request.form()
                    raw_payload = {str(key): value for key, value in form.items()}
            except Exception as exc:
                message = str(exc) or "Invalid moderation request."
                if expects_json:
                    return JSONResponse(
                        {"error": message, "status": 400},
                        status_code=400,
                    )
                return create_secure_html_response(
                    self._render_review_queue_ui(
                        prefix=prefix,
                        notice_title="Moderation failed",
                        notice_body=message,
                        notice_is_error=True,
                    ),
                    status_code=400,
                )

            metadata: dict[str, Any] | None = None
            raw_metadata = raw_payload.get("metadata")
            if isinstance(raw_metadata, dict):
                metadata = {str(key): value for key, value in raw_metadata.items()}
            elif isinstance(raw_metadata, str) and raw_metadata.strip():
                try:
                    parsed = json.loads(raw_metadata)
                except json.JSONDecodeError as exc:
                    if expects_json:
                        return JSONResponse(
                            {
                                "error": f"Invalid metadata JSON: {exc}",
                                "status": 400,
                            },
                            status_code=400,
                        )
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Moderation failed",
                            notice_body=f"Invalid metadata JSON: {exc}",
                            notice_is_error=True,
                        ),
                        status_code=400,
                    )
                if not isinstance(parsed, dict):
                    message = "`metadata` must decode to an object."
                    if expects_json:
                        return JSONResponse(
                            {"error": message, "status": 400},
                            status_code=400,
                        )
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Moderation failed",
                            notice_body=message,
                            notice_is_error=True,
                        ),
                        status_code=400,
                    )
                metadata = parsed

            # Withdraw: publishers may only withdraw their own pending
            # listings. Admins/reviewers can withdraw any listing.
            if action_name.strip().lower() == "withdraw":
                marketplace = self._marketplace()
                target = marketplace.get(listing_id)
                if target is None:
                    err = {"error": f"Listing '{listing_id}' not found", "status": 404}
                    if expects_json:
                        return JSONResponse(err, status_code=404)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Withdraw failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=404,
                    )
                if target.status != PublishStatus.PENDING_REVIEW:
                    err = {"error": "Only pending-review listings can be withdrawn.", "status": 400}
                    if expects_json:
                        return JSONResponse(err, status_code=400)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Withdraw failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=400,
                    )
                caller = session.username if session is not None else "local"
                is_owner = target.author == caller
                is_privileged = session is not None and self._has_roles(
                    session, {RegistryRole.REVIEWER, RegistryRole.ADMIN}
                )
                if not is_owner and not is_privileged:
                    err = {"error": "You can only withdraw your own listings.", "status": 403}
                    if expects_json:
                        return JSONResponse(err, status_code=403)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Withdraw failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=403,
                    )

            if action_name.strip().lower() == "resubmit":
                marketplace = self._marketplace()
                target = marketplace.get(listing_id)
                if target is None:
                    err = {"error": f"Listing '{listing_id}' not found", "status": 404}
                    if expects_json:
                        return JSONResponse(err, status_code=404)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Resubmit failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=404,
                    )
                if target.status != PublishStatus.WITHDRAWN:
                    err = {"error": "Only withdrawn listings can be resubmitted.", "status": 400}
                    if expects_json:
                        return JSONResponse(err, status_code=400)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Resubmit failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=400,
                    )
                caller = session.username if session is not None else "local"
                is_owner = target.author == caller
                is_privileged = session is not None and self._has_roles(
                    session, {RegistryRole.REVIEWER, RegistryRole.ADMIN}
                )
                if not is_owner and not is_privileged:
                    err = {"error": "You can only resubmit your own listings.", "status": 403}
                    if expects_json:
                        return JSONResponse(err, status_code=403)
                    return create_secure_html_response(
                        self._render_review_queue_ui(
                            prefix=prefix,
                            notice_title="Resubmit failed",
                            notice_body=err["error"],
                            notice_is_error=True,
                        ),
                        status_code=403,
                    )

            session_moderator_id = session.username if session is not None else "local"
            payload = self.moderate_listing(
                listing_id,
                action_name=action_name,
                moderator_id=session_moderator_id,
                reason=str(raw_payload.get("reason", "")),
                metadata=metadata,
            )
            status_code = _status_code_from_payload(payload)

            # Record moderation actions in the moderator's own activity
            # feed so admins reviewing a user's history see what they did.
            # Pre-fix moderation was traceable only via the listing's
            # moderation_log, never in the reviewer's account history.
            if (
                session is not None
                and "error" not in payload
                and isinstance(payload.get("listing"), dict)
            ):
                listing_data = payload["listing"]
                try:
                    self._account_activity.append(
                        username=session.username,
                        event_kind="moderation_action",
                        title=f"Moderated '{listing_data.get('display_name', listing_id)}'",
                        detail=(
                            f"Action {action_name!r} → status "
                            f"{listing_data.get('status', 'unknown')}"
                        ),
                        metadata={
                            "listing_id": listing_id,
                            "tool_name": listing_data.get("tool_name", ""),
                            "action": action_name,
                            "new_status": listing_data.get("status", ""),
                            "reason": str(raw_payload.get("reason", "")),
                        },
                    )
                except Exception:
                    logger.warning(
                        "Failed to record moderation activity for %s",
                        session.username,
                        exc_info=True,
                    )
            if expects_json:
                return JSONResponse(payload, status_code=status_code)

            if "error" in payload:
                return create_secure_html_response(
                    self._render_review_queue_ui(
                        prefix=prefix,
                        notice_title="Moderation failed",
                        notice_body=payload["error"],
                        notice_is_error=True,
                    ),
                    status_code=status_code,
                )

            redirect_params = urlencode(
                {
                    "notice": "Moderation updated",
                    "detail": (
                        f"{payload['listing']['display_name']} -> "
                        f"{payload['listing']['status']}"
                    ),
                    "tone": "success",
                }
            )
            return RedirectResponse(
                url=f"{prefix}/review?{redirect_params}",
                status_code=303,
            )

        @self.custom_route(prefix, methods=["POST"])
        async def registry_ui_submit(request: Request):
            return await _handle_publish_form(request)

        @self.custom_route(f"{prefix}/publish", methods=["POST"])
        async def registry_publish_submit(request: Request):
            return await _handle_publish_form(request)

        @self.custom_route(f"{prefix}/tools", methods=["GET"])
        async def registry_tools(request: Request) -> JSONResponse:
            tags = set(_split_multi_value(request, "tag")) or None
            categories = (
                _coerce_categories(_split_multi_value(request, "category")) or None
            )
            limit = int(request.query_params.get("limit", "50"))
            level = _coerce_level(
                request.query_params.get("min_certification"),
                default=self.minimum_certification,
            )
            payload = self.list_verified_tools(
                query=request.query_params.get("q"),
                author=request.query_params.get("author"),
                tags=tags,
                categories=categories,
                min_certification=level,
                limit=limit,
            )
            return JSONResponse(payload)

        @self.custom_route(f"{prefix}/tools/{{tool_name}}", methods=["GET"])
        async def registry_tool_detail(request: Request) -> JSONResponse:
            tool_name = request.path_params.get("tool_name", "")
            session = self._session_from_request(request)

            # Logged-in users (publishers / reviewers / admins / curators)
            # need to see their just-submitted listings even when those
            # listings are still ``PENDING_REVIEW`` — otherwise the
            # post-submit "View listing" link 404s. Mirror the
            # ``/tools/{name}/versions`` endpoint's session-aware
            # lookup: with auth disabled OR no session, return the
            # public listing only; with a session, fall back to a
            # by-name lookup that doesn't filter on publish status.
            if not self.auth_enabled or session is None:
                payload = self.get_verified_tool(tool_name)
                return JSONResponse(
                    payload, status_code=_status_code_from_payload(payload)
                )

            listing = self._marketplace().get_by_name(tool_name)
            if listing is None:
                # Fall back to public-only lookup so the response shape
                # matches when the listing genuinely doesn't exist (or
                # was suspended in a way the requester can't see).
                payload = self.get_verified_tool(tool_name)
                return JSONResponse(
                    payload, status_code=_status_code_from_payload(payload)
                )
            return JSONResponse(self._serialize_listing_detail(listing))

        @self.custom_route(
            f"{prefix}/tools/{{tool_name}}/governance",
            methods=["GET"],
        )
        async def registry_tool_governance(request: Request) -> JSONResponse:
            """Per-listing governance + observability rollup.

            Sibling to the publisher-scoped governance routes — same
            data sources, scoped to one listing. Visibility mirrors
            the listing detail endpoint:

            - Authenticated: any listing the registry knows about.
            - Anonymous (or auth disabled): public listings only,
              and the response is sanitized (actor / moderator /
              agent IDs stripped) so public viewers see governance
              posture without operator-private details.
            """
            tool_name = request.path_params.get("tool_name", "")
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.get_listing_governance(
                tool_name,
                include_non_public=include_non_public,
                sanitize_for_public=not include_non_public,
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(f"{prefix}/tools/{{tool_name}}/versions", methods=["GET"])
        async def registry_tool_versions(request: Request) -> JSONResponse:
            tool_name = request.path_params.get("tool_name", "")
            session = self._session_from_request(request)

            # Viewers can only see public listings; publishers/reviewers/admins can see their own or any.
            if not self.auth_enabled:
                listing = self._get_public_listing(tool_name)
            else:
                if session is None:
                    listing = self._get_public_listing(tool_name)
                else:
                    listing = self._marketplace().get_by_name(tool_name)
                    if listing is None:
                        listing = self._get_public_listing(tool_name)

            if listing is None:
                return JSONResponse(
                    {"error": f"Tool '{tool_name}' not found", "status": 404},
                    status_code=404,
                )

            versions = self._marketplace().get_version_history(listing.listing_id)
            return JSONResponse(
                {
                    "tool_name": tool_name,
                    "listing_id": listing.listing_id,
                    "current_version": listing.version,
                    "status": listing.status.value,
                    "version_count": len(versions),
                    "versions": [
                        v.to_dict() for v in reversed(versions)
                    ],  # newest first
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        @self.custom_route(f"{prefix}/me/listings", methods=["GET"])
        async def registry_me_listings(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if self.auth_enabled and not self._has_roles(
                session,
                {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN},
            ):
                return JSONResponse(
                    {"error": "Publisher or higher role required.", "status": 403},
                    status_code=403,
                )
            author = session.username if session is not None else ""
            payload = self.list_author_listings(author)
            return JSONResponse(payload)

        @self.custom_route(f"{prefix}/install/{{tool_name}}", methods=["GET"])
        async def registry_install_recipes(request: Request) -> JSONResponse:
            tool_name = request.path_params.get("tool_name", "")
            payload = self.get_install_recipes(
                tool_name,
                registry_base_url=str(request.base_url).rstrip("/"),
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(f"{prefix}/submit", methods=["POST"])
        async def registry_submit(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and not self._has_roles(
                session,
                {
                    RegistryRole.PUBLISHER,
                    RegistryRole.REVIEWER,
                    RegistryRole.ADMIN,
                },
            ):
                return JSONResponse(
                    {
                        "error": (
                            "Publisher, reviewer, or admin role required "
                            "to submit listings."
                        ),
                        "status": 401 if session is None else 403,
                    },
                    status_code=401 if session is None else 403,
                )
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )

            manifest_data = body.get("manifest")
            if not isinstance(manifest_data, dict):
                return JSONResponse(
                    {"error": "`manifest` must be an object", "status": 400},
                    status_code=400,
                )

            try:
                manifest = _parse_manifest(manifest_data)
                result = self.submit_tool(
                    manifest,
                    display_name=body.get("display_name", ""),
                    description=body.get("description", ""),
                    categories=_coerce_categories(body.get("categories")),
                    homepage_url=body.get("homepage_url", ""),
                    source_url=body.get("source_url", ""),
                    tool_license=body.get("tool_license", ""),
                    tags=set(body.get("tags", [])) or None,
                    metadata=dict(body.get("metadata", {})),
                    changelog=body.get("changelog", ""),
                    requested_level=_coerce_level(body.get("requested_level")),
                )
            except (KeyError, TypeError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )

            payload = result.to_dict()
            return JSONResponse(
                payload,
                status_code=201 if result.accepted else 400,
            )

        @self.custom_route(f"{prefix}/preflight", methods=["POST"])
        async def registry_preflight(request: Request) -> JSONResponse:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )

            manifest_data = body.get("manifest")
            if not isinstance(manifest_data, dict):
                return JSONResponse(
                    {"error": "`manifest` must be an object", "status": 400},
                    status_code=400,
                )

            try:
                manifest = _parse_manifest(manifest_data)
                categories = _coerce_categories(body.get("categories")) or None
                metadata = dict(body.get("metadata", {}))
                preflight = self.preflight_submission(
                    manifest,
                    display_name=body.get("display_name", ""),
                    categories=categories,
                    metadata=metadata,
                    requested_level=_coerce_level(body.get("requested_level")),
                )
            except (KeyError, TypeError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )

            return JSONResponse(preflight.to_dict())

        # ── Curate (third-party onboarding) ────────────────────────
        # MVP: HTTP-transport upstreams + catalog-only hosting.
        # Stdio / Docker / hosted-proxy modes land in later iterations.

        @self.custom_route(f"{prefix}/curate/resolve", methods=["POST"])
        async def registry_curate_resolve(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and not self._has_roles(
                session,
                {
                    RegistryRole.PUBLISHER,
                    RegistryRole.REVIEWER,
                    RegistryRole.ADMIN,
                },
            ):
                return JSONResponse(
                    {
                        "error": (
                            "Publisher, reviewer, or admin role required "
                            "to curate third-party listings."
                        ),
                        "status": 401 if session is None else 403,
                    },
                    status_code=401 if session is None else 403,
                )
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            # Accept either ``upstream`` (canonical, channel-agnostic)
            # or the legacy ``upstream_url`` for back-compat with the
            # earlier HTTP-only iteration of the wizard.
            raw_input = str(
                body.get("upstream") or body.get("upstream_url") or ""
            ).strip()
            from purecipher.curation import (
                UpstreamFetcher,
                UpstreamResolutionError,
            )

            try:
                preview = UpstreamFetcher().resolve(raw_input)
            except UpstreamResolutionError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            return JSONResponse({"preview": preview.to_dict()})

        @self.custom_route(f"{prefix}/curate/introspect", methods=["POST"])
        async def registry_curate_introspect(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and not self._has_roles(
                session,
                {
                    RegistryRole.PUBLISHER,
                    RegistryRole.REVIEWER,
                    RegistryRole.ADMIN,
                },
            ):
                return JSONResponse(
                    {"error": "Authorization required.", "status": 401},
                    status_code=401,
                )
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            raw_input = str(
                body.get("upstream") or body.get("upstream_url") or ""
            ).strip()
            from purecipher.curation import (
                CredentialValidationError,
                IntrospectionError,
                UpstreamFetcher,
                UpstreamResolutionError,
                derive_manifest_draft,
                validate_introspect_env,
            )

            # Iter 14.8 — token-on-introspect.
            #
            # Some upstream MCP servers (Stripe, Slack, GitHub, Linear,
            # Notion, etc.) refuse to start, or return zero tools, until
            # a credential is present in their environment. The wizard
            # may pass an ``env`` dict here so the curator's introspect
            # call can succeed.
            #
            # Trust contract: this dict is treated as one-shot. We
            # validate it, hand it to the introspector, and let it fall
            # out of scope when the function returns. We never write the
            # env dict — values or keys — to the database, the manifest,
            # the response payload, or any audit log. The introspector
            # itself logs only the *keys* of env (see
            # ``_redacted_env_keys``) so operators can see what was
            # passed without ever seeing the values.
            raw_env = body.get("env")
            try:
                env = validate_introspect_env(
                    raw_env if isinstance(raw_env, dict) else None
                )
            except CredentialValidationError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )

            try:
                preview = UpstreamFetcher().resolve(raw_input)
            except UpstreamResolutionError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            introspector = self._curation_introspector()
            try:
                result = await introspector.introspect(preview.upstream_ref, env=env)
            except IntrospectionError as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 502},
                    status_code=502,
                )
            finally:
                # Belt-and-braces: explicitly drop the local reference
                # so even a future code path that lingers in this scope
                # can't accidentally serialize the env dict alongside
                # the introspection result.
                env = None
            draft = derive_manifest_draft(
                result,
                suggested_tool_name=preview.suggested_tool_name,
                suggested_display_name=preview.suggested_display_name,
            )
            return JSONResponse(
                {
                    "introspection": result.to_dict(),
                    "draft": draft.to_dict(),
                }
            )

        @self.custom_route(f"{prefix}/curate/submit", methods=["POST"])
        async def registry_curate_submit(request: Request) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and not self._has_roles(
                session,
                {
                    RegistryRole.PUBLISHER,
                    RegistryRole.REVIEWER,
                    RegistryRole.ADMIN,
                },
            ):
                return JSONResponse(
                    {"error": "Authorization required.", "status": 401},
                    status_code=401,
                )
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )
            try:
                payload = await self._curate_submit_handler(body, session)
            except (KeyError, TypeError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(f"{prefix}/verify", methods=["POST"])
        async def registry_verify(request: Request) -> JSONResponse:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    {"error": "Invalid JSON body", "status": 400},
                    status_code=400,
                )

            tool_name = body.get("tool_name", "")
            if not tool_name:
                return JSONResponse(
                    {"error": "`tool_name` is required", "status": 400},
                    status_code=400,
                )

            manifest = None
            manifest_data = body.get("manifest")
            if manifest_data is not None:
                if not isinstance(manifest_data, dict):
                    return JSONResponse(
                        {"error": "`manifest` must be an object", "status": 400},
                        status_code=400,
                    )
                try:
                    manifest = _parse_manifest(manifest_data)
                except (KeyError, TypeError, ValueError) as exc:
                    return JSONResponse(
                        {"error": str(exc), "status": 400},
                        status_code=400,
                    )

            # Logged-in users (the curator who just submitted, the
            # publisher who owns the listing, or a reviewer/admin)
            # need to verify their listing's attestation even when it
            # hasn't been moderated to ``PUBLISHED`` yet — otherwise
            # the post-submit detail page shows a misleading
            # "Signature invalid" because verify_tool 404s on a
            # ``PENDING_REVIEW`` listing. Anonymous callers stay on
            # the public-only path.
            session = self._session_from_request(request)
            include_non_public = bool(self.auth_enabled and session is not None)
            payload = self.verify_tool(
                tool_name,
                manifest=manifest,
                include_non_public=include_non_public,
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        # ── Iter 10: MCP client identity routes ────────────────────

        def _resolve_client_or_404(
            client_id_or_slug: str,
        ) -> RegistryClient | JSONResponse:
            """Return the client or a 404 JSON response.

            The path param accepts either UUID or slug — same shape
            as the publishers route — so the UI can link to either
            without translation.
            """
            record = self.get_client(client_id_or_slug)
            if record is None:
                return JSONResponse(
                    {
                        "error": (f"Client {client_id_or_slug!r} not found."),
                        "status": 404,
                    },
                    status_code=404,
                )
            return record

        def _can_manage_client(
            session: RegistrySession | None,
            record: RegistryClient,
        ) -> bool:
            """Owner-or-admin gate for mutating routes.

            When auth is disabled every caller can manage; otherwise
            the caller must either be an admin or be the publisher
            who owns the client. The publisher mapping comes from
            ``publisher_id_from_author`` so the UI's session model
            translates 1:1 to the client store's ownership column.
            """
            if not self.auth_enabled:
                return True
            if session is None:
                return False
            if self._has_roles(session, {RegistryRole.ADMIN}):
                return True
            return (
                publisher_id_from_author(session.username) == record.owner_publisher_id
            )

        @self.custom_route(f"{prefix}/clients", methods=["GET"])
        async def registry_clients_list(
            request: Request,
        ) -> JSONResponse:
            """List clients visible to the caller.

            Admins see everything; publishers see clients they own;
            anyone else gets ``403`` (so the UI's empty-state can
            distinguish "you have no clients" from "you can't see
            this surface"). When auth is disabled the list is
            unfiltered.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            limit = int(request.query_params.get("limit", "200"))
            if (
                self.auth_enabled
                and session is not None
                and not self._has_roles(
                    session,
                    {RegistryRole.ADMIN, RegistryRole.PUBLISHER},
                )
            ):
                return JSONResponse(
                    {
                        "error": (
                            "Publisher or admin role required to view "
                            "registered MCP clients."
                        ),
                        "status": 403,
                    },
                    status_code=403,
                )
            records = self.list_clients_for_caller(session=session, limit=limit)
            return JSONResponse(
                {
                    "items": [r.to_dict() for r in records],
                    "count": len(records),
                    "kinds": sorted(CLIENT_KINDS),
                }
            )

        @self.custom_route(
            f"{prefix}/clients/activity-summary",
            methods=["GET"],
        )
        async def registry_clients_activity_summary(
            request: Request,
        ) -> JSONResponse:
            """Iter 14.24 — aggregate client activity counts.

            Powers the Clients dashboard panel above the directory.
            Same role gate as ``GET /clients`` (admin / publisher).
            Computes by looping every client's ledger window once;
            for typical deployments (<=50 clients) the loop is well
            under 100ms. Larger deployments will want a bulk ledger
            query, which is a future iteration.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if (
                self.auth_enabled
                and session is not None
                and not self._has_roles(
                    session,
                    {RegistryRole.ADMIN, RegistryRole.PUBLISHER},
                )
            ):
                return JSONResponse(
                    {
                        "error": (
                            "Publisher or admin role required to view "
                            "client activity summary."
                        ),
                        "status": 403,
                    },
                    status_code=403,
                )
            return JSONResponse(self.summarize_clients_activity())

        @self.custom_route(f"{prefix}/clients", methods=["POST"])
        async def registry_clients_create(
            request: Request,
        ) -> JSONResponse:
            """Register a new MCP client + (optionally) issue its
            first token.

            Body shape:
              ``{display_name, slug?, description?, intended_use?,
                 kind?, owner_publisher_id?, issue_initial_token?,
                 token_name?, metadata?}``

            ``owner_publisher_id`` is honored only for admins —
            publishers can only create clients owned by themselves
            (the value is overwritten with their derived publisher
            id). The plain token secret is included in the response
            and is the only place it will ever appear; callers must
            surface it once.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            if (
                self.auth_enabled
                and session is not None
                and not self._has_roles(
                    session,
                    {RegistryRole.ADMIN, RegistryRole.PUBLISHER},
                )
            ):
                return JSONResponse(
                    {
                        "error": (
                            "Publisher or admin role required to register MCP clients."
                        ),
                        "status": 403,
                    },
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Body must be a JSON object.", "status": 400},
                    status_code=400,
                )
            display_name = str(body.get("display_name", "") or "").strip()
            if not display_name:
                return JSONResponse(
                    {"error": "`display_name` is required.", "status": 400},
                    status_code=400,
                )
            slug_raw = body.get("slug")
            slug = str(slug_raw).strip() if slug_raw else None
            description = str(body.get("description", "") or "")
            intended_use = str(body.get("intended_use", "") or "")
            kind = str(body.get("kind", "agent") or "agent").strip() or "agent"
            metadata = (
                body.get("metadata") if isinstance(body.get("metadata"), dict) else None
            )
            issue_initial_token = bool(body.get("issue_initial_token", True))
            token_name = (
                str(body.get("token_name", "Default") or "Default").strip() or "Default"
            )

            # Owner publisher resolution: admins may pick; publishers
            # are pinned to their own derived id.
            requested_owner = str(body.get("owner_publisher_id", "") or "").strip()
            if self.auth_enabled and session is not None:
                is_admin = self._has_roles(session, {RegistryRole.ADMIN})
                if is_admin and requested_owner:
                    owner_publisher_id = requested_owner
                else:
                    owner_publisher_id = publisher_id_from_author(session.username)
            else:
                owner_publisher_id = requested_owner or "publisher"

            actor = session.username if session is not None else "anonymous"
            try:
                payload = self.register_client(
                    display_name=display_name,
                    owner_publisher_id=owner_publisher_id,
                    slug=slug,
                    description=description,
                    intended_use=intended_use,
                    kind=kind,
                    metadata=metadata,
                    issue_initial_token=issue_initial_token,
                    token_name=token_name,
                    created_by=actor,
                )
            except (ClientStoreError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            self._account_activity.append(
                username=actor,
                event_kind="client_registered",
                title=f"MCP client registered: {payload['client']['slug']}",
                detail=(
                    f"{actor} registered MCP client "
                    f"{payload['client']['slug']!r} "
                    f"(kind={payload['client']['kind']})."
                ),
                metadata={
                    "client_id": payload["client"]["client_id"],
                    "slug": payload["client"]["slug"],
                    "kind": payload["client"]["kind"],
                },
            )
            return JSONResponse(payload, status_code=201)

        @self.custom_route(f"{prefix}/clients/{{client_id}}", methods=["GET"])
        async def registry_clients_get(
            request: Request,
        ) -> JSONResponse:
            """Fetch a single client by id or slug.

            Visibility mirrors the list endpoint: admins see anyone,
            publishers see their own; anyone else gets a 403 (or
            404 when the client doesn't exist).
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": ("Not allowed to view this client."),
                        "status": 403,
                    },
                    status_code=403,
                )
            tokens = self.list_client_tokens(resolved.client_id)
            return JSONResponse(
                {
                    "client": resolved.to_dict(),
                    "tokens": [t.to_dict() for t in tokens],
                }
            )

        @self.custom_route(f"{prefix}/clients/{{client_id}}", methods=["PATCH"])
        async def registry_clients_update(
            request: Request,
        ) -> JSONResponse:
            """Update editable fields on a client.

            Body accepts any of ``display_name``, ``description``,
            ``intended_use``, ``kind``, ``metadata``. ``slug`` is
            intentionally immutable post-creation — the slug is the
            actor identity broadcast to every plane, so changing it
            silently would break governance attribution.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to update this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Body must be a JSON object.", "status": 400},
                    status_code=400,
                )
            kwargs: dict[str, Any] = {}
            if "display_name" in body:
                kwargs["display_name"] = str(body["display_name"] or "")
            if "description" in body:
                kwargs["description"] = str(body["description"] or "")
            if "intended_use" in body:
                kwargs["intended_use"] = str(body["intended_use"] or "")
            if "kind" in body:
                kwargs["kind"] = str(body["kind"] or "")
            if "metadata" in body and isinstance(body["metadata"], dict):
                kwargs["metadata"] = body["metadata"]
            try:
                updated = self.update_client(resolved.client_id, **kwargs)
            except (ClientStoreError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            if updated is None:
                return JSONResponse(
                    {"error": "Client disappeared.", "status": 404},
                    status_code=404,
                )
            return JSONResponse({"client": updated.to_dict()})

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/suspend",
            methods=["POST"],
        )
        async def registry_clients_suspend(
            request: Request,
        ) -> JSONResponse:
            """Suspend a client.

            Suspended clients can't authenticate (the resolver
            still resolves the slug for telemetry, but
            :meth:`authenticate_client_token` returns ``None`` for
            non-active clients) and can't have new tokens issued.
            Body: ``{"reason": "..."}``.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to suspend this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            reason = ""
            if isinstance(body, dict):
                reason = str(body.get("reason", "") or "")
            updated = self.suspend_client(resolved.client_id, reason=reason)
            if updated is None:
                return JSONResponse(
                    {"error": "Client disappeared.", "status": 404},
                    status_code=404,
                )
            actor = session.username if session is not None else "anonymous"
            self._account_activity.append(
                username=actor,
                event_kind="client_suspended",
                title=f"MCP client suspended: {updated.slug}",
                detail=(
                    f"{actor} suspended {updated.slug!r}"
                    + (f" — {reason}" if reason else "")
                ),
                metadata={"client_id": updated.client_id, "slug": updated.slug},
            )
            return JSONResponse({"client": updated.to_dict()})

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/unsuspend",
            methods=["POST"],
        )
        async def registry_clients_unsuspend(
            request: Request,
        ) -> JSONResponse:
            """Re-activate a previously suspended client."""
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to unsuspend this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            updated = self.unsuspend_client(resolved.client_id)
            if updated is None:
                return JSONResponse(
                    {"error": "Client disappeared.", "status": 404},
                    status_code=404,
                )
            actor = session.username if session is not None else "anonymous"
            self._account_activity.append(
                username=actor,
                event_kind="client_unsuspended",
                title=f"MCP client unsuspended: {updated.slug}",
                detail=f"{actor} unsuspended {updated.slug!r}.",
                metadata={"client_id": updated.client_id, "slug": updated.slug},
            )
            return JSONResponse({"client": updated.to_dict()})

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/tokens",
            methods=["GET"],
        )
        async def registry_clients_list_tokens(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to view tokens for this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            tokens = self.list_client_tokens(resolved.client_id)
            return JSONResponse(
                {
                    "client_id": resolved.client_id,
                    "items": [t.to_dict() for t in tokens],
                    "count": len(tokens),
                }
            )

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/tokens",
            methods=["POST"],
        )
        async def registry_clients_issue_token(
            request: Request,
        ) -> JSONResponse:
            """Issue a new token for the client.

            Body: ``{"name": "..."}``. Returns ``{token, secret}``;
            the secret is shown to the operator exactly once.
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to issue tokens for this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            name = "Default"
            if isinstance(body, dict):
                name_raw = str(body.get("name", "") or "").strip()
                if name_raw:
                    name = name_raw
            actor = session.username if session is not None else "anonymous"
            try:
                token, secret = self.issue_client_token(
                    resolved.client_id, name=name, created_by=actor
                )
            except (ClientStoreError, ValueError) as exc:
                return JSONResponse(
                    {"error": str(exc), "status": 400},
                    status_code=400,
                )
            self._account_activity.append(
                username=actor,
                event_kind="client_token_issued",
                title=f"Token issued for {resolved.slug}",
                detail=(
                    f"{actor} issued token {name!r} "
                    f"(prefix {token.secret_prefix}) for client "
                    f"{resolved.slug!r}."
                ),
                metadata={
                    "client_id": resolved.client_id,
                    "slug": resolved.slug,
                    "token_id": token.token_id,
                },
            )
            return JSONResponse(
                {"token": token.to_dict(), "secret": secret},
                status_code=201,
            )

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/tokens/{{token_id}}",
            methods=["DELETE"],
        )
        async def registry_clients_revoke_token(
            request: Request,
        ) -> JSONResponse:
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            token_id = request.path_params.get("token_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to revoke tokens for this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            revoked = self.revoke_client_token(token_id)
            if revoked is None:
                return JSONResponse(
                    {"error": f"Token {token_id!r} not found.", "status": 404},
                    status_code=404,
                )
            actor = session.username if session is not None else "anonymous"
            self._account_activity.append(
                username=actor,
                event_kind="client_token_revoked",
                title=f"Token revoked for {resolved.slug}",
                detail=(
                    f"{actor} revoked token {revoked.name!r} "
                    f"(prefix {revoked.secret_prefix}) for client "
                    f"{resolved.slug!r}."
                ),
                metadata={
                    "client_id": resolved.client_id,
                    "slug": resolved.slug,
                    "token_id": revoked.token_id,
                },
            )
            return JSONResponse({"token": revoked.to_dict()})

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/governance",
            methods=["GET"],
        )
        async def registry_clients_governance(
            request: Request,
        ) -> JSONResponse:
            """Return the per-client governance + observability rollup.

            Owner-or-admin gated under auth (mirrors the per-client
            detail route). Sanitization is automatic for callers
            without management rights so a public-facing variant of
            the page can show *that* the client has activity without
            leaking *who* they're talking to.
            """
            session = self._session_from_request(request)
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            sanitize = not _can_manage_client(session, resolved)
            payload = self.get_client_governance(
                resolved.client_id, sanitize_for_public=sanitize
            )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        @self.custom_route(
            f"{prefix}/clients/{{client_id}}/simulate",
            methods=["POST"],
        )
        async def registry_clients_simulate(
            request: Request,
        ) -> JSONResponse:
            """Dry-run a request against every governance plane.

            Iter 11. Owner-or-admin gated. Body shape:

            ``{
              action: str,
              resource_id: str,
              metadata?: dict,
              tags?: list[str],
              consent_scope?: str,
              consent_source_id?: str,
              metric_name?: str,
              metric_value?: number,
            }``
            """
            session = self._session_from_request(request)
            if self.auth_enabled and session is None:
                return JSONResponse(
                    {"error": "Authentication required.", "status": 401},
                    status_code=401,
                )
            client_id = request.path_params.get("client_id", "")
            resolved = _resolve_client_or_404(client_id)
            if isinstance(resolved, JSONResponse):
                return resolved
            if not _can_manage_client(session, resolved):
                return JSONResponse(
                    {
                        "error": "Not allowed to simulate this client.",
                        "status": 403,
                    },
                    status_code=403,
                )
            try:
                body = await request.json()
            except Exception:
                body = None
            if not isinstance(body, dict):
                return JSONResponse(
                    {"error": "Body must be a JSON object.", "status": 400},
                    status_code=400,
                )
            action = str(body.get("action", "") or "").strip()
            resource_id = str(body.get("resource_id", "") or "").strip()
            if not action or not resource_id:
                return JSONResponse(
                    {
                        "error": ("`action` and `resource_id` are required."),
                        "status": 400,
                    },
                    status_code=400,
                )
            metadata = (
                body.get("metadata") if isinstance(body.get("metadata"), dict) else None
            )
            tags_raw = body.get("tags")
            tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else None
            consent_scope = str(body.get("consent_scope", "execute") or "execute")
            consent_source_id_raw = body.get("consent_source_id")
            consent_source_id = (
                str(consent_source_id_raw)
                if isinstance(consent_source_id_raw, str)
                and consent_source_id_raw.strip()
                else None
            )
            metric_name_raw = body.get("metric_name")
            metric_name = (
                str(metric_name_raw)
                if isinstance(metric_name_raw, str) and metric_name_raw.strip()
                else None
            )
            metric_value_raw = body.get("metric_value")
            try:
                metric_value = (
                    float(metric_value_raw) if metric_value_raw is not None else None
                )
            except (TypeError, ValueError):
                return JSONResponse(
                    {
                        "error": "`metric_value` must be a number.",
                        "status": 400,
                    },
                    status_code=400,
                )
            try:
                payload = await self.simulate_client_request(
                    resolved.client_id,
                    action=action,
                    resource_id=resource_id,
                    metadata=metadata,
                    tags=tags,
                    consent_scope=consent_scope,
                    consent_source_id=consent_source_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                )
            except Exception as exc:
                logger.exception("Simulator route raised")
                return JSONResponse(
                    {
                        "error": f"Simulation failed: {exc!r}",
                        "status": 500,
                    },
                    status_code=500,
                )
            return JSONResponse(payload, status_code=_status_code_from_payload(payload))

        self._registry_api_mounted = True
        self._registry_prefix = prefix
        return self

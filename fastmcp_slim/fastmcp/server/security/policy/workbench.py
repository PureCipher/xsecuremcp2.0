"""Policy workbench helpers for UI-driven management flows.

This module keeps higher-level management concepts out of the core engine:

- reusable policy bundles
- environment profiles for migrations
- analytics summaries for the policy console
- human-friendly change summaries between policy snapshots
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp.server.security.policy.serialization import (
    describe_policy_config,
)

logger = logging.getLogger(__name__)

# Iter 14.21 — operators can drop additional ``*.json`` policy
# bundle files in this directory and they get merged with the
# built-in bundles at lookup time. Set via env var so deployments
# (Docker, Kubernetes, bare metal) can configure it without
# touching code. Empty / unset means "built-ins only".
_BUNDLES_DIR_ENV = "PURECIPHER_POLICY_BUNDLES_DIR"


@dataclass(frozen=True)
class PolicyEnvironmentProfile:
    """Environment guidance for policy promotion and migration."""

    environment_id: str
    title: str
    description: str
    goals: tuple[str, ...]
    required_controls: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "title": self.title,
            "description": self.description,
            "goals": list(self.goals),
            "required_controls": list(self.required_controls),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PolicyBundle:
    """Reusable policy pack for common SecureMCP operating modes."""

    bundle_id: str
    title: str
    summary: str
    description: str
    risk_posture: str
    recommended_environments: tuple[str, ...]
    tags: tuple[str, ...]
    providers: tuple[dict[str, Any], ...]
    pack_version: str = ""
    regulation_reference: str = ""
    source_reviewed_at: str = ""
    coverage_note: str = ""
    source_urls: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "risk_posture": self.risk_posture,
            "recommended_environments": list(self.recommended_environments),
            "tags": list(self.tags),
            "pack_version": self.pack_version,
            "regulation_reference": self.regulation_reference,
            "source_reviewed_at": self.source_reviewed_at,
            "coverage_note": self.coverage_note,
            "source_urls": list(self.source_urls),
            "provider_count": len(self.providers),
            "provider_summaries": [
                describe_policy_config(provider) for provider in self.providers
            ],
            "providers": [dict(provider) for provider in self.providers],
        }


_ENVIRONMENTS: tuple[PolicyEnvironmentProfile, ...] = (
    PolicyEnvironmentProfile(
        environment_id="development",
        title="Development",
        description="Fast iteration with enough guardrails to catch unsafe rules early.",
        goals=(
            "Keep the chain easy to edit.",
            "Surface risky allow-all rules before they escape dev.",
        ),
        required_controls=(
            "At least one reviewer-aware access rule",
            "A denylist for obvious admin-only surfaces",
        ),
        warnings=(
            "Allow-all rules are acceptable only for short-lived local testing.",
            "Time-based controls can get in the way of local iteration.",
        ),
    ),
    PolicyEnvironmentProfile(
        environment_id="staging",
        title="Staging",
        description="Pre-production validation with production-like access patterns.",
        goals=(
            "Mirror production policy shape closely.",
            "Simulate realistic reviewer and publisher workflows before promotion.",
        ),
        required_controls=(
            "Role-aware access rules",
            "A denylist for sensitive resources",
            "Rate limiting on shared endpoints",
        ),
        warnings=(
            "Large chain replacements should be simulated before approval.",
            "Unassigned or stale proposals should be cleared before promotion.",
        ),
    ),
    PolicyEnvironmentProfile(
        environment_id="production",
        title="Production",
        description="Tight governance for live SecureMCP surfaces and shared tooling.",
        goals=(
            "Enforce least privilege.",
            "Require explicit reviewer ownership and predictable rollout risk.",
        ),
        required_controls=(
            "Role-aware access rules",
            "A denylist for sensitive resources",
            "Rate limiting",
            "Simulation before approval",
        ),
        warnings=(
            "Allow-all rules are a production risk.",
            "Missing rate limiting increases blast radius during abuse or drift.",
            "Replacing the whole chain should be treated as a high-attention change.",
        ),
    ),
)


_BUNDLES: tuple[PolicyBundle, ...] = (
    # ── Compliance Bundles ────────────────────────────────────
    PolicyBundle(
        bundle_id="gdpr-data-protection",
        title="GDPR Request Validation",
        summary="Validate personal-data requests using trusted subject-specific evidence.",
        description="Checks legal basis, special-category conditions, criminal-offence authority, purpose, scope, current subject restrictions, recipient arrangements and international transfers. Requires exact grants and a server-side evidence resolver. Significant automated decisions and restriction overrides are unsupported.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "gdpr", "privacy", "eu", "data-protection"),
        pack_version="2.0.0",
        regulation_reference="Regulation (EU) 2016/679; EUR-Lex consolidated text 2016-05-04",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504",
        ),
        coverage_note="Request-time safeguards only, not full GDPR certification. Trusted adapters verify legal conditions and enforce output controls. National-law assessments, rights workflows, notices, DPIAs and supervisory processes remain external. Empty grants/issuer/scope deny execution; active policies are not automatically migrated.",
        providers=(
            {
                "type": "gdpr_request",
                "policy_id": "gdpr-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "gdpr-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 100,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="hipaa-health-data",
        title="HIPAA Request Validation",
        summary="Validate PHI requests with trusted patient-specific evidence.",
        description="Checks permitted grounds, minimum necessary or a verified exception, patient restrictions, authorizations, recipient authority and business-associate scope. Requires exact grants and a trusted server-side resolver. No global business-hours gate.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "hipaa", "healthcare", "phi", "us"),
        pack_version="2.0.0",
        regulation_reference="45 CFR Parts 160 and 164; HHS guidance reviewed September 6, 2026",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html",
            "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164",
            "https://www.hhs.gov/hipaa/for-professionals/special-topics/reproductive-health/final-rule-fact-sheet/index.html",
        ),
        coverage_note="Request safeguards only, not full HIPAA certification. External systems verify legal conditions and enforce output controls. Part 2 records and authorization/restriction exceptions are unsupported. HHS reports most 2024 reproductive-health provisions vacated; no blanket attestation requirement is imposed. Empty grants/issuer/scope deny execution; active policies are not automatically migrated.",
        providers=(
            {
                "type": "hipaa_request",
                "policy_id": "hipaa-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "hipaa-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 60,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="soc2-trust-services",
        title="SOC 2 Request Validation",
        summary="Validate MCP requests against trusted access and operational safeguards.",
        description="Checks all operation effects, data classification, access, capacity, processing integrity, confidentiality, privacy and system-change authorization. Requires a trusted server-side resolver and exact grants. Ordinary reads do not require a change window.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "soc2", "trust-services", "saas", "cloud"),
        pack_version="2.0.0",
        regulation_reference="AICPA 2017 Trust Services Criteria (SOC 2 framework, not a regulation)",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022",
        ),
        coverage_note="Selected request-time safeguards aligned to all five trust service categories; not full SOC 2 audit coverage or certification. External systems verify facts and enforce output controls. Governance, physical security, audits and approval workflows remain external. Empty grants/issuer/scope deny execution; active policies are not automatically migrated.",
        providers=(
            {
                "type": "soc2_request",
                "policy_id": "soc2-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "soc2-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 150,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="zero-trust-lockdown",
        title="Zero Trust Request Validation",
        summary="Exact actor, resource and action grants with fresh trusted posture evidence.",
        description="Requires explicit grants and current session, device and risk verification. No role, network location or metadata flag confers implicit access. Configure a server-side evidence resolver, trusted issuers and server/tenant scope before activation.",
        risk_posture="locked_down",
        recommended_environments=("production",),
        tags=("zero-trust", "locked-down", "high-security"),
        pack_version="2.0.0",
        regulation_reference="NIST SP 800-207 (August 2020)",
        source_reviewed_at="2026-09-06",
        source_urls=("https://www.nist.gov/publications/zero-trust-architecture",),
        coverage_note="Request authorization only; posture evidence must be authenticated externally. This does not implement a complete Zero Trust architecture or continuous session termination. Empty configuration denies all access, including discovery. Configure explicit administrative recovery access before activation. Policy changes are persisted through normal policy versioning; evidence is rechecked per request.",
        providers=(
            {
                "type": "zero_trust",
                "policy_id": "zero-trust-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "zero-trust-rate-limit",
                "version": "1.0.0",
                "max_requests": 50,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="pci-dss-cardholder-data",
        title="PCI DSS Request Validation",
        summary="Validate account-data operations, PAN protection and sensitive authentication data restrictions.",
        description="Requires trusted request-bound evidence and exact actor/resource/action grants. Evaluates display, processing, transmission, storage and deletion safeguards. Preserves rate limiting; institutional workflows and PCI certification are outside scope.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "pci-dss", "payment", "cardholder", "financial"),
        pack_version="2.0.0",
        regulation_reference="PCI DSS v4.0.1 (June 2024)",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://www.pcisecuritystandards.org/document_library/",
            "https://www.pcisecuritystandards.org/faqs/1154/",
            "https://www.pcisecuritystandards.org/faqs/1492/",
        ),
        coverage_note="Request safeguards only, not PCI certification or payload inspection. The trusted verifier must validate actual scope and server protections. This conservative pack does not support issuer-specific SAD retention exceptions or SAD disclosure to MCP clients. Empty issuer/scope/grants deny access until configured; existing policies are not automatically replaced.",
        providers=(
            {
                "type": "pci_request",
                "policy_id": "pci-dss-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "pci-dss-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 60,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="ccpa-consumer-privacy",
        title="CCPA/CPRA Request Validation",
        summary="Validate consumer-data requests against current trusted privacy evidence.",
        description="Checks every affected consumer, purpose, minimization, recipient restrictions, opt-outs/GPC, minors, sensitive use and consumer access safeguards. Requires exact grants and a server-side evidence resolver. ADMT is conservatively blocked pending a dedicated policy.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "ccpa", "cpra", "privacy", "california", "us"),
        pack_version="2.0.0",
        regulation_reference="CCPA as amended; 11 CCR Division 6 Chapter 1 (effective January 1, 2026)",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://cppa.ca.gov/pdf/20260101_ccpa_statute.pdf",
            "https://cppa.ca.gov/regulations/pdf/ccpa_statute_eff_20260101.pdf",
        ),
        coverage_note="Request validation only; no consumer-rights workflow or business-wide certification. Trusted adapters verify complete data scope, current preferences, notices/contracts and applicable risk evidence. ADMT and legal-exemption overrides are unsupported. Empty grants/issuer/scope deny execution. Existing active policies are not migrated automatically.",
        providers=(
            {
                "type": "ccpa_request",
                "policy_id": "ccpa-request-validation",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "ccpa-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 100,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="ferpa-student-records",
        title="FERPA Request Validation",
        summary="Validate MCP disclosures against trusted FERPA request evidence.",
        description="Evaluates consent, the 16 disclosure exceptions, and de-identification. Requires a server-side evidence resolver and explicit trusted issuer/server scope configuration. Missing evidence denies execution; institutional workflows remain external.",
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "ferpa", "education", "us"),
        pack_version="2.0.0",
        regulation_reference="20 U.S.C. 1232g; 34 CFR Part 99",
        source_reviewed_at="2026-09-06",
        source_urls=(
            "https://studentprivacy.ed.gov/ferpa",
            "https://www.ecfr.gov/current/title-34/subtitle-A/part-99",
        ),
        coverage_note="Request-validation coverage only. External systems must authenticate the evidence and verify the applicable facts. This pack does not manage institutional workflows or certify institution-wide compliance. Empty issuer/scope settings deny execution until configured. Existing active policies are not migrated automatically.",
        providers=(
            {
                "type": "ferpa_request",
                "policy_id": "ferpa-request-validation",
                "version": "2.0.0",
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="registry-balanced",
        title="Balanced Registry Guardrails",
        summary="Explicit access grants and current request posture for registry deployments.",
        description="Uses the shared Zero Trust evaluator for exact actor/resource/action grants and trusted session, device and risk evidence, plus a request-rate limit. Role labels and tool wildcards do not grant access. Configure grants for the intended operations before activation.",
        risk_posture="balanced",
        recommended_environments=("development", "staging"),
        tags=("registry", "starter", "balanced"),
        pack_version="2.0.0",
        regulation_reference="PureCipher registry access baseline v2.0.0 (product policy)",
        source_reviewed_at="2026-09-06",
        source_urls=("https://github.com/PureCipher/xsecuremcp2.0",),
        coverage_note="Access-admission baseline only. Does not establish publication, read-only behavior or legal data authority; compose the relevant policies. Uses the existing trusted Zero Trust resolver. Empty grants/issuer/scope deny access. No workflows are implemented and active policy chains are not migrated automatically.",
        providers=(
            {
                "type": "zero_trust",
                "policy_id": "registry-balanced-access",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "registry-balanced-rate-limit",
                "version": "1.0.0",
                "max_requests": 250,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="registry-strict-change-control",
        title="Strict Change Control",
        summary="Production-minded controls for reviewer-owned policy and listing changes.",
        description=(
            "Builds on the balanced bundle and adds business-hours control for "
            "sensitive review and policy actions."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("registry", "strict", "production"),
        providers=(
            {
                "type": "allowlist",
                "policy_id": "registry-strict-allowlist",
                "version": "1.0.0",
                "allowed": [
                    "tool:*",
                    "registry:submit",
                    "registry:review",
                    "registry:policy",
                ],
            },
            {
                "type": "rbac",
                "policy_id": "registry-strict-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "publisher": ["submit_listing"],
                    "reviewer": ["review_listing", "manage_policy"],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "registry-strict-denylist",
                "version": "1.0.0",
                "denied": ["admin-panel"],
            },
            {
                "type": "rate_limit",
                "policy_id": "registry-strict-rate-limit",
                "version": "1.0.0",
                "max_requests": 120,
                "window_seconds": 1800,
            },
            {
                "type": "time_based",
                "policy_id": "registry-strict-business-hours",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 8,
                "end_hour": 19,
                "utc_offset_hours": 0,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="published-tools-only",
        title="Published Tools Only",
        summary="Permit only verified published tools with read-only effects.",
        description="Requires current publication/revocation evidence, a verified signed manifest and exact component binding. Allows tool discovery and read/compute calls; rejects mutating tools and registry administration. Requires exact grants and a server-side publication resolver.",
        risk_posture="locked_down",
        recommended_environments=("development", "production"),
        tags=("catalog", "readonly", "viewer"),
        pack_version="2.0.0",
        regulation_reference="PureCipher published-tool safeguards v2.0.0 (product policy)",
        source_reviewed_at="2026-09-06",
        source_urls=("https://github.com/PureCipher/xsecuremcp2.0",),
        coverage_note="Requires authoritative publication and runtime effect verification. Client tags/readOnlyHint are insufficient. Read-only does not authorize sensitive data access; compose applicable data policies. Empty grants/issuer/scope deny; active policies are not automatically migrated.",
        providers=(
            {
                "type": "published_tools",
                "policy_id": "published-tools-only",
                "version": "2.0.0",
                "grants": [],
                "trusted_issuers": [],
                "scope_id": "",
                "max_evidence_age_seconds": 60,
            },
            {
                "type": "rate_limit",
                "policy_id": "catalog-only-rate-limit",
                "version": "1.0.0",
                "max_requests": 300,
                "window_seconds": 3600,
            },
        ),
    ),
)


# ── Iter 14.21 — JSON-on-disk bundle loader ──────────────────────


class BundleLoadError(ValueError):
    """A bundle JSON file failed validation.

    Raised by :func:`_validate_bundle_payload` per-file and caught
    by :func:`load_bundles_from_disk`, which logs each error and
    skips the bad file rather than aborting the whole load. Custom
    type so callers (and tests) can distinguish it from generic
    ``ValueError`` from elsewhere in the loader.
    """


def _validate_bundle_payload(payload: Any, *, source: str) -> PolicyBundle:
    """Validate one decoded JSON payload and build a PolicyBundle.

    Strict on the required fields (``bundle_id``, ``title``,
    ``summary``, ``providers``); lenient on the optional ones,
    defaulting to empty strings/tuples so a minimal valid file
    just needs the four required keys plus a sensible
    ``description``.

    The ``source`` argument is included in error messages so
    operators can find the offending file quickly.

    Raises:
        BundleLoadError: with a curator-friendly message if any
            required field is missing or has the wrong type.
    """
    if not isinstance(payload, dict):
        raise BundleLoadError(
            f"{source}: bundle JSON must decode to an object, "
            f"got {type(payload).__name__}."
        )

    def _required_str(key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BundleLoadError(
                f"{source}: required field {key!r} is missing or "
                "not a non-empty string."
            )
        return value

    bundle_id = _required_str("bundle_id")
    title = _required_str("title")
    summary = _required_str("summary")

    providers_raw = payload.get("providers")
    if not isinstance(providers_raw, list) or not providers_raw:
        raise BundleLoadError(
            f"{source}: required field 'providers' must be a "
            "non-empty list of provider config objects."
        )
    providers: list[dict[str, Any]] = []
    for idx, entry in enumerate(providers_raw):
        if not isinstance(entry, dict):
            raise BundleLoadError(
                f"{source}: providers[{idx}] must be an object, "
                f"got {type(entry).__name__}."
            )
        providers.append(dict(entry))

    description = payload.get("description") or summary
    risk_posture = payload.get("risk_posture") or "balanced"

    def _str_tuple(key: str) -> tuple[str, ...]:
        value = payload.get(key) or []
        if not isinstance(value, list):
            raise BundleLoadError(
                f"{source}: optional field {key!r} must be a list "
                f"of strings, got {type(value).__name__}."
            )
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise BundleLoadError(f"{source}: {key!r} entries must be strings.")
            out.append(item)
        return tuple(out)

    def _optional_str(key: str) -> str:
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise BundleLoadError(f"{source}: {key!r} must be a string.")
        return value

    return PolicyBundle(
        pack_version=_optional_str("pack_version"),
        regulation_reference=_optional_str("regulation_reference"),
        source_reviewed_at=_optional_str("source_reviewed_at"),
        coverage_note=_optional_str("coverage_note"),
        source_urls=_str_tuple("source_urls"),
        bundle_id=bundle_id,
        title=title,
        summary=summary,
        description=str(description),
        risk_posture=str(risk_posture),
        recommended_environments=_str_tuple("recommended_environments"),
        tags=_str_tuple("tags"),
        providers=tuple(providers),
    )


def load_bundles_from_disk(
    bundles_dir: str | os.PathLike[str] | None,
) -> tuple[PolicyBundle, ...]:
    """Scan a directory for ``*.json`` files and return validated bundles.

    Iter 14.21 — Operators can drop new bundles into a
    well-known directory without forking the framework. Each file
    is validated independently; a single bad file logs a warning
    and is skipped, rather than nuking the whole load.

    Bundle IDs are deduplicated within the disk set: if two files
    declare the same ``bundle_id``, only the first encountered
    (sorted by filename) wins, with a warning for the loser. The
    caller (:func:`_effective_bundles`) handles collisions with the
    built-in set separately.

    Returns an empty tuple when ``bundles_dir`` is ``None``, the
    empty string, or a path that doesn't exist — never raises in
    those cases. Real directories are scanned non-recursively;
    ``*.json`` only.
    """
    if bundles_dir is None:
        return ()
    path = Path(str(bundles_dir)).expanduser()
    if not path.is_dir():
        # An unset / wrong path is a config issue, not an error
        # that should knock the registry over. Log INFO so it shows
        # in startup logs without alarming operators.
        if str(bundles_dir).strip():
            logger.info(
                "Policy bundles directory %r is not a directory; "
                "no on-disk bundles loaded.",
                str(bundles_dir),
            )
        return ()

    loaded: list[PolicyBundle] = []
    seen_ids: set[str] = set()
    # Sort by filename so the order is deterministic across runs
    # — important because dedup picks the first occurrence.
    for entry in sorted(path.glob("*.json")):
        try:
            raw = entry.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Couldn't read policy bundle file %s: %s", entry, exc)
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Skipping invalid JSON in policy bundle file %s: %s",
                entry,
                exc,
            )
            continue
        try:
            bundle = _validate_bundle_payload(payload, source=str(entry))
        except BundleLoadError as exc:
            logger.warning("Skipping malformed policy bundle: %s", exc)
            continue
        if bundle.bundle_id in seen_ids:
            logger.warning(
                "Duplicate bundle_id %r in %s; keeping the first "
                "occurrence and dropping this file.",
                bundle.bundle_id,
                entry,
            )
            continue
        seen_ids.add(bundle.bundle_id)
        loaded.append(bundle)
    return tuple(loaded)


def _effective_bundles() -> tuple[PolicyBundle, ...]:
    """Built-in bundles + on-disk bundles, in that order.

    Built-ins always win on bundle_id collision so an operator
    can't accidentally shadow a vetted compliance bundle (GDPR,
    HIPAA, SOC 2, etc.) with a misconfigured local file.
    """
    extras = load_bundles_from_disk(os.environ.get(_BUNDLES_DIR_ENV))
    if not extras:
        return _BUNDLES
    builtin_ids = {b.bundle_id for b in _BUNDLES}
    safe_extras: list[PolicyBundle] = []
    for bundle in extras:
        if bundle.bundle_id in builtin_ids:
            logger.warning(
                "On-disk bundle %r collides with a built-in bundle; "
                "the built-in version is being kept and the on-disk "
                "file is being skipped.",
                bundle.bundle_id,
            )
            continue
        safe_extras.append(bundle)
    return _BUNDLES + tuple(safe_extras)


def list_policy_bundles() -> list[dict[str, Any]]:
    """Return reusable policy bundles for the management UI."""

    return [bundle.to_dict() for bundle in _effective_bundles()]


def get_policy_bundle(bundle_id: str) -> dict[str, Any] | None:
    """Return one bundle by identifier."""

    for bundle in _effective_bundles():
        if bundle.bundle_id == bundle_id:
            return bundle.to_dict()
    return None


def list_policy_environments() -> list[dict[str, Any]]:
    """Return known environment profiles for migration guidance."""

    return [environment.to_dict() for environment in _ENVIRONMENTS]


def get_policy_environment(environment_id: str) -> dict[str, Any] | None:
    """Return one environment profile by identifier."""

    for environment in _ENVIRONMENTS:
        if environment.environment_id == environment_id:
            return environment.to_dict()
    return None


def summarize_policy_chain_delta(
    source_configs: list[dict[str, Any]],
    target_configs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a UI-friendly summary of how two chains differ."""

    changed: list[dict[str, Any]] = []
    shared = min(len(source_configs), len(target_configs))
    for index in range(shared):
        source = source_configs[index]
        target = target_configs[index]
        if source != target:
            changed.append(
                {
                    "index": index,
                    "from": describe_policy_config(source),
                    "to": describe_policy_config(target),
                    "from_type": str(
                        source.get("type") or source.get("composition") or ""
                    ),
                    "to_type": str(
                        target.get("type") or target.get("composition") or ""
                    ),
                }
            )

    added = [
        {
            "index": index,
            "summary": describe_policy_config(config),
            "type": str(config.get("type") or config.get("composition") or ""),
        }
        for index, config in enumerate(target_configs[shared:], start=shared)
    ]
    removed = [
        {
            "index": index,
            "summary": describe_policy_config(config),
            "type": str(config.get("type") or config.get("composition") or ""),
        }
        for index, config in enumerate(source_configs[shared:], start=shared)
    ]

    return {
        "source_provider_count": len(source_configs),
        "target_provider_count": len(target_configs),
        "changed_count": len(changed),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed": changed,
        "added": added,
        "removed": removed,
    }


def build_policy_risks(
    *,
    provider_configs: list[dict[str, Any]],
    pending_count: int = 0,
    stale_count: int = 0,
    deny_rate: float = 0.0,
    recent_alert_count: int = 0,
    changed_count: int = 0,
) -> list[dict[str, str]]:
    """Return a small set of human-facing risk flags for the policy UI."""

    types = {
        str(config.get("type") or config.get("composition") or "")
        for config in provider_configs
    }
    risks: list[dict[str, str]] = []

    if "allow_all" in types:
        risks.append(
            {
                "level": "high",
                "title": "Allow-all rule is active",
                "detail": "An allow-all provider weakens least-privilege controls in shared environments.",
            }
        )
    if "rbac" not in types and "role_based" not in types:
        risks.append(
            {
                "level": "medium",
                "title": "No role-aware rule in the chain",
                "detail": "Reviewer, publisher, and admin actions are easier to drift without RBAC coverage.",
            }
        )
    if "rate_limit" not in types:
        risks.append(
            {
                "level": "medium",
                "title": "No rate limiting configured",
                "detail": "Shared registry actions have no per-actor throttle in the current chain.",
            }
        )
    if stale_count > 0:
        risks.append(
            {
                "level": "medium",
                "title": "Stale proposals are waiting",
                "detail": f"{stale_count} proposal(s) are pinned to an older live version.",
            }
        )
    if pending_count >= 4:
        risks.append(
            {
                "level": "low",
                "title": "Review queue is backing up",
                "detail": f"{pending_count} proposals are waiting for review or deployment.",
            }
        )
    if deny_rate >= 0.4 or recent_alert_count >= 2:
        risks.append(
            {
                "level": "high",
                "title": "Policy is actively blocking a lot of traffic",
                "detail": "High deny rates or repeated alerts can indicate drift, abuse, or an overly strict rollout.",
            }
        )
    elif deny_rate >= 0.2:
        risks.append(
            {
                "level": "medium",
                "title": "Deny rate is elevated",
                "detail": "Recent policy decisions are blocking more traffic than normal.",
            }
        )
    if changed_count >= 3:
        risks.append(
            {
                "level": "medium",
                "title": "Recent rollout changed several rules at once",
                "detail": "Larger updates deserve simulation and reviewer ownership before promotion.",
            }
        )

    return risks


def build_environment_recommendations(
    *,
    environment_id: str,
    provider_configs: list[dict[str, Any]],
) -> list[str]:
    """Suggest follow-up steps for a target environment."""

    types = {
        str(config.get("type") or config.get("composition") or "")
        for config in provider_configs
    }
    recommendations: list[str] = []

    if environment_id == "production":
        if "rbac" not in types and "role_based" not in types:
            recommendations.append(
                "Add an RBAC rule before promoting this chain to production."
            )
        if "rate_limit" not in types:
            recommendations.append(
                "Introduce a rate-limit rule before production rollout."
            )
        if "allow_all" in types:
            recommendations.append(
                "Replace allow-all access with explicit allowlists or resource-scoped rules."
            )
    elif environment_id == "staging":
        if "denylist" not in types:
            recommendations.append(
                "Add a denylist for sensitive resources before staging validation."
            )
        if "time_based" not in types and "temporal" not in types:
            recommendations.append(
                "Consider time-based controls if reviewers only manage changes in staffed hours."
            )
    elif environment_id == "development":
        if "allow_all" in types:
            recommendations.append(
                "Keep allow-all rules short-lived and pair them with a migration plan to staging."
            )

    if not recommendations:
        recommendations.append(
            "This chain already lines up well with the selected environment profile."
        )
    return recommendations

"""Production-grade compliance rule packs.

Each module in this package encodes one regulatory framework as a
:class:`~fastmcp.server.security.policy.policies.compliance_rule.ComplianceRulePolicy`.
Rules are sourced from the authoritative publication of the regulating
body — EUR-Lex for EU regulations, the eCFR for US federal rules,
the AICPA for SOC 2 Trust Services Criteria, the ISO for ISO/IEC
standards, NIST CSRC for federal control catalogues, PCI SSC for
PCI DSS, and California Legislative Information for state statutes.

Every rule carries a :class:`~fastmcp.server.security.policy.provider.Citation`
stamped with ``source`` (short framework id), ``article`` (the exact
section/article/control reference as written in the official text),
``url`` (canonical link to the authoritative source), ``version``
(the edition the rule was authored against), and ``retrieved_at``
(the date the rule author last verified the cited text).

Scope — "enforceable at tool-call boundary":

All packs are explicitly scoped to rules the MCP kernel can
mechanically verify from (actor, action, resource, tags, metadata).
Procedural obligations (DPIAs, board-level risk acceptance, periodic
audits, policy documents) are not encoded; they belong in
organizational governance, not per-call authorization.

Public API::

    from fastmcp.server.security.policy.compliance_packs import (
        build_pack, list_available_packs,
    )

    gdpr = build_pack("GDPR")
    all_names = list_available_packs()

When an operator opts a listing into a pack via the plugin registry,
the framework name used at the UI layer matches the ``framework``
attribute on the returned policy (``"GDPR"``, ``"HIPAA"``, etc.).
"""

from __future__ import annotations

from collections.abc import Callable

from fastmcp.server.security.policy.compliance_packs.ccpa import (
    build_ccpa_policy,
)
from fastmcp.server.security.policy.compliance_packs.dora import (
    build_dora_policy,
)
from fastmcp.server.security.policy.compliance_packs.ferpa import (
    build_ferpa_policy,
)
from fastmcp.server.security.policy.compliance_packs.gdpr import (
    build_gdpr_policy,
)
from fastmcp.server.security.policy.compliance_packs.hipaa import (
    build_hipaa_policy,
)
from fastmcp.server.security.policy.compliance_packs.iso_27001 import (
    build_iso_27001_policy,
)
from fastmcp.server.security.policy.compliance_packs.nis2 import (
    build_nis2_policy,
)
from fastmcp.server.security.policy.compliance_packs.nist_800_53 import (
    build_nist_800_53_policy,
)
from fastmcp.server.security.policy.compliance_packs.pci_dss import (
    build_pci_dss_policy,
)
from fastmcp.server.security.policy.compliance_packs.soc2 import (
    build_soc2_policy,
)
from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
)

# Map canonical framework names → factory. Aliases are included so
# UI surfaces that render "GDPR" / "gdpr" / "EU GDPR" all resolve to
# the same pack. The canonical name (first key hit) is returned by
# ``list_available_packs()``.
_PACK_FACTORIES: dict[str, Callable[[], ComplianceRulePolicy]] = {
    "GDPR": build_gdpr_policy,
    "HIPAA": build_hipaa_policy,
    "SOC2": build_soc2_policy,
    "PCI-DSS": build_pci_dss_policy,
    "CCPA": build_ccpa_policy,
    "FERPA": build_ferpa_policy,
    "ISO-27001": build_iso_27001_policy,
    "NIST-800-53": build_nist_800_53_policy,
    "NIS2": build_nis2_policy,
    "DORA": build_dora_policy,
}


def _normalize_name(name: str) -> str:
    """Normalize user-supplied pack names.

    Tolerates casing and common separators (``"PCI DSS"``,
    ``"pci_dss"``, ``"pci-dss"`` all resolve to the canonical
    ``"PCI-DSS"``). A leading/trailing whitespace is stripped; empty
    input returns empty so the lookup fails deterministically.
    """
    return name.strip().upper().replace("_", "-").replace(" ", "-")


def build_pack(name: str) -> ComplianceRulePolicy:
    """Construct the compliance pack identified by ``name``.

    Args:
        name: A framework identifier — ``"GDPR"``, ``"HIPAA"``,
            ``"SOC2"``, ``"PCI-DSS"``, ``"CCPA"``, ``"FERPA"``,
            ``"ISO-27001"``, ``"NIST-800-53"``, ``"NIS2"``, or
            ``"DORA"``. Casing and separator style are tolerated.

    Raises:
        KeyError: When ``name`` doesn't match any available pack.

    Returns:
        A fresh :class:`ComplianceRulePolicy` instance; callers get
        their own copy so per-listing configuration never mutates a
        shared pack.
    """
    normalized = _normalize_name(name)
    factory = _PACK_FACTORIES.get(normalized)
    if factory is None:
        available = ", ".join(sorted(_PACK_FACTORIES))
        raise KeyError(
            f"No compliance pack named {name!r}. Available: {available}"
        )
    return factory()


def list_available_packs() -> list[str]:
    """Return the canonical framework names for every pack.

    Sorted alphabetically so downstream UI listings are stable.
    """
    return sorted(_PACK_FACTORIES)


__all__ = [
    "build_ccpa_policy",
    "build_dora_policy",
    "build_ferpa_policy",
    "build_gdpr_policy",
    "build_hipaa_policy",
    "build_iso_27001_policy",
    "build_nis2_policy",
    "build_nist_800_53_policy",
    "build_pack",
    "build_pci_dss_policy",
    "build_soc2_policy",
    "list_available_packs",
]

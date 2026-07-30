"""Tests for the production-grade compliance packs.

Each pack is validated at three levels:

1. **Parity** — all 10 packs load, carry a non-zero rule set, and
   stamp a :class:`Citation` on every rule. Pack construction is the
   authoring API; if a rule lost its citation during editing, this
   suite catches it before it reaches the audit log.

2. **Framework-specific deny/allow scenarios** — one concrete
   tag+metadata combination per pack that proves the DENY path fires
   against a cited rule and the ALLOW path fires when the required
   metadata is supplied. These are intentionally minimal; exhaustive
   per-article coverage belongs in dedicated pack tests.

3. **Citation end-to-end** — drives a pack through the
   :class:`PolicyEngine` with a :class:`PolicyAuditLog` attached and
   confirms the :class:`Citation` rides the :class:`AuditEntry` to
   the log, exactly as the structured-citation contract promises.

The aim is to keep this file small and forever-green — the *content*
of the rules lives in the pack modules; the tests here prove the
plumbing between ComplianceRuleSpec → PolicyResult → AuditEntry stays
intact.
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.policy.audit import PolicyAuditLog
from fastmcp.server.security.policy.compliance_packs import (
    build_pack,
    list_available_packs,
)
from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
)
from fastmcp.server.security.policy.provider import (
    Citation,
    PolicyDecision,
    PolicyEvaluationContext,
)

# --------------------------------------------------------------------
# Parity: every pack is well-formed, cited, and namespaced.
# --------------------------------------------------------------------


class TestPackRegistryParity:
    """All 10 packs load and carry at least one cited rule."""

    EXPECTED = {
        "GDPR",
        "HIPAA",
        "SOC2",
        "PCI-DSS",
        "CCPA",
        "FERPA",
        "ISO-27001",
        "NIST-800-53",
        "NIS2",
        "DORA",
    }

    def test_list_available_packs_is_canonical(self):
        assert set(list_available_packs()) == self.EXPECTED

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_pack_builds(self, name: str):
        pack = build_pack(name)
        assert isinstance(pack, ComplianceRulePolicy)
        assert pack.framework, f"{name}: framework label must be set"
        assert pack.rules, f"{name}: must carry at least one rule"

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_every_rule_is_cited(self, name: str):
        pack = build_pack(name)
        for rule in pack.rules:
            assert rule.citation is not None, (
                f"{name}.{rule.name} is missing a Citation"
            )
            citation = rule.citation
            assert isinstance(citation, Citation)
            # Canonicals: source non-empty, article non-empty,
            # URL present, version present.
            assert citation.source, f"{name}.{rule.name}: empty citation.source"
            assert citation.article, f"{name}.{rule.name}: empty citation.article"
            assert citation.url.startswith(("http://", "https://")), (
                f"{name}.{rule.name}: citation.url must be absolute"
            )
            assert citation.version, f"{name}.{rule.name}: citation.version must be set"

    def test_build_pack_normalizes_case_and_separators(self):
        # Each of these should resolve to the GDPR pack.
        for alias in ("gdpr", "GDPR", "Gdpr", " gdpr "):
            assert build_pack(alias).framework == "GDPR"

    def test_build_pack_normalizes_pci_dss_separator(self):
        for alias in ("PCI-DSS", "pci-dss", "PCI_DSS", "pci dss"):
            assert build_pack(alias).framework == "PCI-DSS"

    def test_build_pack_rejects_unknown_name(self):
        with pytest.raises(KeyError):
            build_pack("SOX")


# --------------------------------------------------------------------
# Framework-specific scenarios: one DENY + one ALLOW per pack.
#
# These don't try to exhaust each framework's rules — they prove the
# pack is wired correctly: a representative tag activates the
# expected rule, missing metadata produces DENY with the cited
# article, and satisfying metadata produces ALLOW.
# --------------------------------------------------------------------


def _ctx(
    *,
    tags: set[str],
    metadata: dict | None = None,
    action: str = "call_tool",
    resource_id: str = "some-resource",
) -> PolicyEvaluationContext:
    return PolicyEvaluationContext(
        actor_id="agent-test",
        action=action,
        resource_id=resource_id,
        tags=frozenset(tags),
        metadata=metadata or {},
    )


class TestGDPRScenarios:
    async def test_pii_without_legal_basis_is_denied(self):
        pack = build_pack("GDPR")
        result = await pack.evaluate(_ctx(tags={"pii"}))
        assert result.decision == PolicyDecision.DENY
        assert any(c.article.startswith("Article") for c in result.citations)

    async def test_pii_with_complete_metadata_is_allowed(self):
        pack = build_pack("GDPR")
        result = await pack.evaluate(
            _ctx(
                tags={"pii"},
                metadata={
                    "processing_purpose": "support",
                    "data_minimization_scope": "customer_support",
                    "legal_basis": "contract",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestHIPAAScenarios:
    async def test_phi_without_metadata_is_denied(self):
        pack = build_pack("HIPAA")
        result = await pack.evaluate(_ctx(tags={"phi"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations
        assert result.citations[0].source == "HIPAA"

    async def test_phi_with_tpo_and_minimum_necessary_allows(self):
        pack = build_pack("HIPAA")
        result = await pack.evaluate(
            _ctx(
                tags={"phi"},
                metadata={
                    "purpose": "patient-record-review",
                    "minimum_necessary_justified": "true",
                    "actor_role": "healthcare_provider",
                    "tpo_purpose": "treatment",
                    "user_identifier": "clinician-123",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestSOC2Scenarios:
    async def test_soc2_scoped_without_principal_is_denied(self):
        pack = build_pack("SOC2")
        result = await pack.evaluate(_ctx(tags={"soc2_scoped"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "SOC2"

    async def test_soc2_scoped_with_all_metadata_allows(self):
        pack = build_pack("SOC2")
        result = await pack.evaluate(
            _ctx(
                tags={"soc2_scoped"},
                metadata={
                    "authenticated_principal": "alice@example.com",
                    "role": "engineer",
                    "identity_provider": "okta",
                    "trace_id": "trace-1",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestPCIDSSScenarios:
    async def test_pan_storage_without_protection_is_denied(self):
        pack = build_pack("PCI-DSS")
        result = await pack.evaluate(_ctx(tags={"pan_storage"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "PCI-DSS"

    async def test_pan_storage_with_tokenization_allows(self):
        pack = build_pack("PCI-DSS")
        result = await pack.evaluate(
            _ctx(
                tags={"pan_storage"},
                metadata={"pan_protection": "tokenization"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestCCPAScenarios:
    async def test_pi_sale_without_opt_out_check_denied(self):
        pack = build_pack("CCPA")
        result = await pack.evaluate(_ctx(tags={"pi_sale"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "CCPA"

    async def test_pi_sale_with_opt_out_status_allows(self):
        pack = build_pack("CCPA")
        result = await pack.evaluate(
            _ctx(
                tags={"pi_sale"},
                metadata={"opt_out_status": "not_opted_out"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestFERPAScenarios:
    async def test_education_record_without_authority_denied(self):
        pack = build_pack("FERPA")
        result = await pack.evaluate(_ctx(tags={"education_record"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "FERPA"

    async def test_education_record_with_consent_allows(self):
        pack = build_pack("FERPA")
        result = await pack.evaluate(
            _ctx(
                tags={"education_record"},
                metadata={"disclosure_authority": "written_consent"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestISO27001Scenarios:
    async def test_scoped_asset_without_policy_denied(self):
        pack = build_pack("ISO-27001")
        result = await pack.evaluate(_ctx(tags={"iso27001_scoped"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "ISO-27001"

    async def test_scoped_asset_with_policy_allows(self):
        pack = build_pack("ISO-27001")
        result = await pack.evaluate(
            _ctx(
                tags={"iso27001_scoped"},
                metadata={
                    "access_policy_id": "pol-001",
                    "log_stream_id": "logs-1",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestNIST80053Scenarios:
    async def test_moderate_scope_without_account_denied(self):
        pack = build_pack("NIST-800-53")
        result = await pack.evaluate(_ctx(tags={"nist_moderate"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "NIST-800-53"

    async def test_moderate_scope_with_account_allows(self):
        pack = build_pack("NIST-800-53")
        result = await pack.evaluate(
            _ctx(
                tags={"nist_moderate"},
                metadata={
                    "account_id": "acct-123",
                    "account_type": "individual",
                    "authorization_decision_id": "pdp-1",
                    "granted_scope": "read",
                    "audit_event_type": "read",
                    "source_network_address": "10.0.0.1",
                    "outcome": "success",
                    "audit_correlation_id": "corr-1",
                    "unique_user_identifier": "user-1",
                    "authentication_assurance_level": "AAL2",
                    "transmission_protection": "tls_1_2",
                    "at_rest_protection": "fips_140_encryption",
                    "monitoring_sensor_id": "sensor-1",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestNIS2Scenarios:
    async def test_essential_entity_without_risk_assessment_denied(self):
        pack = build_pack("NIS2")
        result = await pack.evaluate(_ctx(tags={"nis2_essential_entity"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "NIS2"

    async def test_essential_entity_with_risk_assessment_allows(self):
        pack = build_pack("NIS2")
        result = await pack.evaluate(
            _ctx(
                tags={"nis2_essential_entity"},
                metadata={"risk_assessment_id": "ra-1"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW


class TestDORAScenarios:
    async def test_scoped_system_without_framework_denied(self):
        pack = build_pack("DORA")
        result = await pack.evaluate(_ctx(tags={"dora_scoped_system"}))
        assert result.decision == PolicyDecision.DENY
        assert result.citations[0].source == "DORA"

    async def test_scoped_system_with_framework_and_telemetry_allows(self):
        pack = build_pack("DORA")
        result = await pack.evaluate(
            _ctx(
                tags={"dora_scoped_system"},
                metadata={
                    "ict_risk_framework_id": "fw-1",
                    "detection_telemetry_id": "td-1",
                },
            )
        )
        assert result.decision == PolicyDecision.ALLOW


# --------------------------------------------------------------------
# Citation end-to-end: PolicyEngine → PolicyAuditLog.
# --------------------------------------------------------------------


class TestCitationPipeline:
    async def test_audit_entry_carries_citation_on_deny(self):
        pack = build_pack("GDPR")
        audit = PolicyAuditLog()
        engine = PolicyEngine(providers=[pack], audit_log=audit)
        # No metadata → DENY under GDPR Art 5/6.
        await engine.evaluate(_ctx(tags={"pii"}))

        entries = audit.query(decision=PolicyDecision.DENY, limit=1)
        assert entries, "audit log should have a deny entry"
        entry = entries[0]
        assert entry.citations, "deny entry must carry citations"
        assert entry.citations[0].source == "GDPR"
        # Primary citation should be the rule that actually produced
        # the deny — the ordering contract from compliance_rule.py.
        assert entry.citations[0].article.startswith("Article")

    async def test_audit_entry_carries_citation_on_allow(self):
        pack = build_pack("HIPAA")
        audit = PolicyAuditLog()
        engine = PolicyEngine(providers=[pack], audit_log=audit)
        await engine.evaluate(
            _ctx(
                tags={"phi"},
                metadata={
                    "purpose": "patient-review",
                    "minimum_necessary_justified": "true",
                    "actor_role": "healthcare_provider",
                    "tpo_purpose": "treatment",
                    "user_identifier": "clinician-1",
                },
            )
        )
        entries = audit.query(decision=PolicyDecision.ALLOW, limit=1)
        assert entries, "audit log should have an allow entry"
        entry = entries[0]
        assert entry.citations
        assert entry.citations[0].source == "HIPAA"

    def test_citation_to_dict_is_stable_json_shape(self):
        pack = build_pack("SOC2")
        citation = pack.rules[0].citation
        assert citation is not None
        payload = citation.to_dict()
        assert set(payload) == {
            "source",
            "article",
            "url",
            "version",
            "retrieved_at",
        }

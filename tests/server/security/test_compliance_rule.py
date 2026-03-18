"""Tests for the declarative compliance rule engine."""

from __future__ import annotations

import pytest

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
)


def _ctx(
    *,
    resource_id: str = "tool:test",
    tags: frozenset[str] | None = None,
    metadata: dict | None = None,
) -> PolicyEvaluationContext:
    return PolicyEvaluationContext(
        actor_id="test-actor",
        action="call_tool",
        resource_id=resource_id,
        tags=tags or frozenset(),
        metadata=metadata or {},
    )


def _gdpr_rule() -> ComplianceRuleSpec:
    return ComplianceRuleSpec(
        name="legal_basis_required",
        description="PII requires legal basis",
        tags=frozenset({"pii", "personal_data", "gdpr_regulated"}),
        checks=(
            MetadataCheck(
                metadata_key="legal_basis",
                allowed_values=frozenset(
                    {"consent", "contract", "legal_obligation",
                     "legitimate_interests", "public_interest", "vital_interests"}
                ),
            ),
        ),
        deny_message="GDPR: Missing or invalid legal basis",
        allow_message="GDPR: Access permitted under legal basis",
    )


def _hipaa_rule() -> ComplianceRuleSpec:
    return ComplianceRuleSpec(
        name="authorized_role_required",
        description="PHI requires authorized role and purpose",
        tags=frozenset({"phi", "health_data", "hipaa_regulated"}),
        checks=(
            MetadataCheck(
                metadata_key="actor_role",
                allowed_values=frozenset(
                    {"healthcare_provider", "business_associate",
                     "health_plan", "healthcare_clearinghouse"}
                ),
            ),
            MetadataCheck(
                metadata_key="purpose",
            ),
        ),
        deny_message="HIPAA: Unauthorized PHI access",
        allow_message="HIPAA: PHI access permitted",
    )


class TestComplianceRuleEngine:
    """Core evaluation logic for the compliance rule engine."""

    @pytest.mark.anyio
    async def test_no_rules_defers(self) -> None:
        policy = ComplianceRulePolicy(rules=[], framework="Test")
        result = await policy.evaluate(_ctx())
        assert result.decision == PolicyDecision.DEFER

    @pytest.mark.anyio
    async def test_no_matching_tags_defers(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule()],
            framework="GDPR",
        )
        result = await policy.evaluate(_ctx(tags=frozenset({"unrelated"})))
        assert result.decision == PolicyDecision.DEFER
        assert "not applicable" in result.reason

    @pytest.mark.anyio
    async def test_matching_tags_missing_metadata_denies(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule()],
            framework="GDPR",
        )
        result = await policy.evaluate(_ctx(tags=frozenset({"pii"})))
        assert result.decision == PolicyDecision.DENY
        assert "GDPR" in result.reason

    @pytest.mark.anyio
    async def test_matching_tags_invalid_metadata_denies(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule()],
            framework="GDPR",
        )
        result = await policy.evaluate(
            _ctx(
                tags=frozenset({"pii"}),
                metadata={"legal_basis": "because_i_said_so"},
            )
        )
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.anyio
    async def test_matching_tags_valid_metadata_allows(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule()],
            framework="GDPR",
        )
        result = await policy.evaluate(
            _ctx(
                tags=frozenset({"personal_data"}),
                metadata={"legal_basis": "consent"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW
        assert "compliance:legal_basis_required" in result.constraints

    @pytest.mark.anyio
    async def test_hipaa_multiple_checks_all_must_pass(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_hipaa_rule()],
            framework="HIPAA",
        )

        only_role = await policy.evaluate(
            _ctx(
                tags=frozenset({"phi"}),
                metadata={"actor_role": "healthcare_provider"},
            )
        )
        assert only_role.decision == PolicyDecision.DENY

        only_purpose = await policy.evaluate(
            _ctx(
                tags=frozenset({"phi"}),
                metadata={"purpose": "treatment"},
            )
        )
        assert only_purpose.decision == PolicyDecision.DENY

        both = await policy.evaluate(
            _ctx(
                tags=frozenset({"phi"}),
                metadata={
                    "actor_role": "healthcare_provider",
                    "purpose": "treatment",
                },
            )
        )
        assert both.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_require_all_rules_false_any_passing_allows(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule(), _hipaa_rule()],
            framework="Multi",
            require_all_rules=False,
        )
        result = await policy.evaluate(
            _ctx(
                tags=frozenset({"pii", "phi"}),
                metadata={"legal_basis": "consent"},
            )
        )
        assert result.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_require_all_rules_true_one_failing_denies(self) -> None:
        policy = ComplianceRulePolicy(
            rules=[_gdpr_rule(), _hipaa_rule()],
            framework="Multi",
            require_all_rules=True,
        )
        result = await policy.evaluate(
            _ctx(
                tags=frozenset({"pii", "phi"}),
                metadata={"legal_basis": "consent"},
            )
        )
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.anyio
    async def test_optional_metadata_check(self) -> None:
        rule = ComplianceRuleSpec(
            name="optional_check",
            description="Optional metadata is fine if missing",
            tags=frozenset({"tagged"}),
            checks=(
                MetadataCheck(
                    metadata_key="optional_field",
                    required=False,
                    allowed_values=frozenset({"yes"}),
                ),
            ),
        )
        policy = ComplianceRulePolicy(rules=[rule])

        missing = await policy.evaluate(_ctx(tags=frozenset({"tagged"})))
        assert missing.decision == PolicyDecision.ALLOW

        present_valid = await policy.evaluate(
            _ctx(tags=frozenset({"tagged"}), metadata={"optional_field": "yes"})
        )
        assert present_valid.decision == PolicyDecision.ALLOW

        present_invalid = await policy.evaluate(
            _ctx(tags=frozenset({"tagged"}), metadata={"optional_field": "no"})
        )
        assert present_invalid.decision == PolicyDecision.DENY


class TestComplianceRuleDeclarative:
    """Test building compliance_rule from JSON config via load_policy."""

    def test_load_gdpr_from_config(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy

        policy = load_policy({
            "type": "compliance_rule",
            "policy_id": "gdpr-test",
            "version": "1.0.0",
            "framework": "GDPR",
            "rules": [
                {
                    "name": "legal_basis",
                    "description": "Require legal basis",
                    "tags": ["pii"],
                    "checks": [
                        {
                            "metadata_key": "legal_basis",
                            "allowed_values": ["consent", "contract"],
                        }
                    ],
                    "deny_message": "Missing legal basis",
                    "allow_message": "Legal basis valid",
                }
            ],
        })
        assert isinstance(policy, ComplianceRulePolicy)
        assert policy.framework == "GDPR"
        assert len(policy.rules) == 1
        assert policy.rules[0].name == "legal_basis"
        assert "pii" in policy.rules[0].tags

    def test_load_hipaa_from_config(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy

        policy = load_policy({
            "type": "compliance_rule",
            "policy_id": "hipaa-test",
            "framework": "HIPAA",
            "rules": [
                {
                    "name": "phi_gate",
                    "description": "PHI requires role + purpose",
                    "tags": ["phi", "health_data"],
                    "checks": [
                        {
                            "metadata_key": "actor_role",
                            "allowed_values": ["healthcare_provider"],
                        },
                        {"metadata_key": "purpose"},
                    ],
                    "deny_message": "HIPAA violation",
                }
            ],
        })
        assert isinstance(policy, ComplianceRulePolicy)
        assert policy.framework == "HIPAA"
        assert len(policy.rules[0].checks) == 2

    @pytest.mark.anyio
    async def test_loaded_policy_evaluates_correctly(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy

        policy = load_policy({
            "type": "compliance_rule",
            "policy_id": "eval-test",
            "framework": "Test",
            "rules": [
                {
                    "name": "auth_check",
                    "description": "Require auth token",
                    "tags": ["secure"],
                    "checks": [
                        {"metadata_key": "auth_token"},
                    ],
                    "deny_message": "Auth required",
                }
            ],
        })

        denied = await policy.evaluate(_ctx(tags=frozenset({"secure"})))
        assert denied.decision == PolicyDecision.DENY

        allowed = await policy.evaluate(
            _ctx(
                tags=frozenset({"secure"}),
                metadata={"auth_token": "abc123"},
            )
        )
        assert allowed.decision == PolicyDecision.ALLOW


class TestComplianceRuleSerialization:
    """Test round-tripping compliance_rule through serialization."""

    def test_round_trip_serialize_deserialize(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.serialization import (
            policy_provider_to_config,
        )

        original_config = {
            "type": "compliance_rule",
            "policy_id": "roundtrip-test",
            "version": "2.0.0",
            "framework": "GDPR",
            "rules": [
                {
                    "name": "legal_basis",
                    "description": "Require legal basis",
                    "tags": ["pii", "personal_data"],
                    "checks": [
                        {
                            "metadata_key": "legal_basis",
                            "allowed_values": ["consent", "contract"],
                        }
                    ],
                    "deny_message": "Missing legal basis",
                    "allow_message": "Legal basis valid",
                }
            ],
        }

        provider = load_policy(original_config)
        serialized = policy_provider_to_config(provider)

        assert serialized["type"] == "compliance_rule"
        assert serialized["framework"] == "GDPR"
        assert serialized["policy_id"] == "roundtrip-test"
        assert serialized["version"] == "2.0.0"
        assert len(serialized["rules"]) == 1

        rule = serialized["rules"][0]
        assert rule["name"] == "legal_basis"
        assert set(rule["tags"]) == {"pii", "personal_data"}
        assert rule["checks"][0]["metadata_key"] == "legal_basis"
        assert set(rule["checks"][0]["allowed_values"]) == {"consent", "contract"}

        rebuilt = load_policy(serialized)
        assert isinstance(rebuilt, ComplianceRulePolicy)
        assert rebuilt.framework == "GDPR"
        assert rebuilt.rules[0].name == "legal_basis"


class TestBundleComplianceRuleIntegration:
    """Verify GDPR and HIPAA bundles load and evaluate correctly."""

    @pytest.mark.anyio
    async def test_gdpr_bundle_core_provider_evaluates(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("gdpr-data-protection")
        assert bundle is not None
        core_config = bundle["providers"][0]
        assert core_config["type"] == "compliance_rule"

        provider = load_policy(core_config)

        untagged = await provider.evaluate(_ctx(tags=frozenset({"safe"})))
        assert untagged.decision == PolicyDecision.DEFER

        missing_basis = await provider.evaluate(
            _ctx(tags=frozenset({"pii"}))
        )
        assert missing_basis.decision == PolicyDecision.DENY

        valid_basis = await provider.evaluate(
            _ctx(
                tags=frozenset({"pii"}),
                metadata={"legal_basis": "consent"},
            )
        )
        assert valid_basis.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_hipaa_bundle_core_provider_evaluates(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("hipaa-health-data")
        assert bundle is not None
        core_config = bundle["providers"][0]
        assert core_config["type"] == "compliance_rule"

        provider = load_policy(core_config)

        untagged = await provider.evaluate(_ctx(tags=frozenset({"safe"})))
        assert untagged.decision == PolicyDecision.DEFER

        missing_all = await provider.evaluate(
            _ctx(tags=frozenset({"phi"}))
        )
        assert missing_all.decision == PolicyDecision.DENY

        role_only = await provider.evaluate(
            _ctx(
                tags=frozenset({"phi"}),
                metadata={"actor_role": "healthcare_provider"},
            )
        )
        assert role_only.decision == PolicyDecision.DENY

        valid_access = await provider.evaluate(
            _ctx(
                tags=frozenset({"phi"}),
                metadata={
                    "actor_role": "healthcare_provider",
                    "purpose": "treatment",
                },
            )
        )
        assert valid_access.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_pci_dss_bundle_core_provider_evaluates(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("pci-dss-cardholder-data")
        assert bundle is not None
        core_config = bundle["providers"][0]
        assert core_config["type"] == "compliance_rule"

        provider = load_policy(core_config)

        untagged = await provider.evaluate(_ctx(tags=frozenset({"safe"})))
        assert untagged.decision == PolicyDecision.DEFER

        missing_all = await provider.evaluate(
            _ctx(tags=frozenset({"cardholder_data"}))
        )
        assert missing_all.decision == PolicyDecision.DENY

        role_only = await provider.evaluate(
            _ctx(
                tags=frozenset({"cardholder_data"}),
                metadata={"processor_role": "payment_processor"},
            )
        )
        assert role_only.decision == PolicyDecision.DENY

        valid_access = await provider.evaluate(
            _ctx(
                tags=frozenset({"payment_data"}),
                metadata={
                    "processor_role": "payment_processor",
                    "business_justification": "transaction_processing",
                },
            )
        )
        assert valid_access.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_ccpa_bundle_core_provider_evaluates(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("ccpa-consumer-privacy")
        assert bundle is not None
        core_config = bundle["providers"][0]
        assert core_config["type"] == "compliance_rule"

        provider = load_policy(core_config)

        untagged = await provider.evaluate(_ctx(tags=frozenset({"safe"})))
        assert untagged.decision == PolicyDecision.DEFER

        missing_purpose = await provider.evaluate(
            _ctx(tags=frozenset({"consumer_pi"}))
        )
        assert missing_purpose.decision == PolicyDecision.DENY

        valid_access = await provider.evaluate(
            _ctx(
                tags=frozenset({"consumer_pi"}),
                metadata={
                    "processing_purpose": "service_delivery",
                    "business_role": "business_operator",
                },
            )
        )
        assert valid_access.decision == PolicyDecision.ALLOW

        # Opt-out rule: data_sharing tag denied when opt-out not verified
        opt_out_blocked = await provider.evaluate(
            _ctx(tags=frozenset({"data_sharing"}))
        )
        assert opt_out_blocked.decision == PolicyDecision.DENY

        opt_out_clear = await provider.evaluate(
            _ctx(
                tags=frozenset({"data_sharing"}),
                metadata={"consumer_opt_out_verified": "false"},
            )
        )
        assert opt_out_clear.decision == PolicyDecision.ALLOW

    @pytest.mark.anyio
    async def test_ferpa_bundle_core_provider_evaluates(self) -> None:
        from fastmcp.server.security.policy.declarative import load_policy
        from fastmcp.server.security.policy.workbench import get_policy_bundle

        bundle = get_policy_bundle("ferpa-student-records")
        assert bundle is not None
        core_config = bundle["providers"][0]
        assert core_config["type"] == "compliance_rule"

        provider = load_policy(core_config)

        untagged = await provider.evaluate(_ctx(tags=frozenset({"safe"})))
        assert untagged.decision == PolicyDecision.DEFER

        missing_all = await provider.evaluate(
            _ctx(tags=frozenset({"student_record"}))
        )
        assert missing_all.decision == PolicyDecision.DENY

        valid_access = await provider.evaluate(
            _ctx(
                tags=frozenset({"student_record"}),
                metadata={
                    "official_role": "teacher",
                    "educational_interest": "grade_reporting",
                },
            )
        )
        assert valid_access.decision == PolicyDecision.ALLOW

        # Directory info with opt-out check (require_all_rules=False)
        dir_info_blocked = await provider.evaluate(
            _ctx(
                tags=frozenset({"directory_information"}),
                metadata={"student_opted_out": "true"},
            )
        )
        assert dir_info_blocked.decision == PolicyDecision.DENY

        dir_info_allowed = await provider.evaluate(
            _ctx(
                tags=frozenset({"directory_information"}),
                metadata={"student_opted_out": "false"},
            )
        )
        assert dir_info_allowed.decision == PolicyDecision.ALLOW

    def test_all_bundles_are_fully_declarative(self) -> None:
        """No bundle should use python_class — all must be JSON-declarative."""
        from fastmcp.server.security.policy.workbench import list_policy_bundles

        for bundle in list_policy_bundles():
            for provider in bundle["providers"]:
                assert provider.get("type") != "python_class", (
                    f"Bundle {bundle['bundle_id']} still uses python_class "
                    f"in provider {provider.get('policy_id', '?')}"
                )

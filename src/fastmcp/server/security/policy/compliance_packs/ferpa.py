"""FERPA (34 CFR Part 99) compliance pack.

Encodes the subset of the Family Educational Rights and Privacy Act
regulations at 34 CFR Part 99 that can be verified at an MCP tool-call
boundary. FERPA protects the privacy of student education records
maintained by schools that receive U.S. Department of Education
funding.

Each rule carries a :class:`Citation` pointing at the Office of the
Federal Register eCFR edition of 34 CFR Part 99, the authoritative
text.

Scope decisions — explicitly not encoded here:

- § 99.7 notice of rights is a publication requirement.
- § 99.32 recordkeeping for disclosures is an organizational record,
  not a per-call check (though we do require a disclosure_record_id
  in the relevant rule below to make the recordkeeping possible).
- § 99.63 office for reviewing complaints is a consumer channel.

What IS encoded:

- § 99.3 — core definitions (education record, directory info, PII).
- § 99.10 — right to inspect and review.
- § 99.30 — prior written consent required for disclosure.
- § 99.31 — exceptions: school officials with legitimate educational
  interest, directory information, health/safety emergency, etc.
- § 99.35 — disclosure to authorized representatives conducting
  audits or evaluations.

Sources:

- eCFR Title 34 Part 99:
  https://www.ecfr.gov/current/title-34/subtitle-A/part-99
- Department of Education FERPA guidance:
  https://studentprivacy.ed.gov/ferpa
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_ECFR_PART_99 = "https://www.ecfr.gov/current/title-34/subtitle-A/part-99"
_VERSION = "34 CFR Part 99"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="FERPA",
        article=article,
        url=_ECFR_PART_99,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── § 99.10 — right to inspect and review ─────────────────────────


_SEC_99_10_INSPECT = ComplianceRuleSpec(
    name="sec99_10_inspect_request",
    description=(
        "34 CFR 99.10(a) — an educational agency or institution shall "
        "permit a parent or eligible student to inspect and review the "
        "student's education records. Inspection workflows must carry "
        "the verified request id."
    ),
    tags=frozenset({"ferpa_inspection_workflow"}),
    checks=(
        MetadataCheck(metadata_key="inspection_request_id"),
    ),
    deny_message=(
        "FERPA 34 CFR 99.10(a): Inspection workflow requires an "
        "inspection_request_id."
    ),
    citation=_cite("34 CFR 99.10(a)"),
)


# ── § 99.30 — prior written consent required ──────────────────────


_SEC_99_30_CONSENT = ComplianceRuleSpec(
    name="sec99_30_prior_written_consent",
    description=(
        "34 CFR 99.30(a) — the parent or eligible student shall provide "
        "a signed and dated written consent before an educational "
        "agency or institution discloses PII from the student's "
        "education records, unless the disclosure meets one of the "
        "§ 99.31 exceptions."
    ),
    tags=frozenset(
        {"education_record", "student_pii", "ferpa_regulated"}
    ),
    checks=(
        MetadataCheck(
            metadata_key="disclosure_authority",
            allowed_values=frozenset(
                {
                    "written_consent",
                    "ferpa_exception",
                }
            ),
        ),
    ),
    deny_message=(
        "FERPA 34 CFR 99.30: Disclosure of PII from education records "
        "requires disclosure_authority=written_consent, or "
        "=ferpa_exception with a qualifying § 99.31 basis."
    ),
    citation=_cite("34 CFR 99.30(a)"),
)


# ── § 99.31 — exceptions to consent ────────────────────────────────


_SEC_99_31_EXCEPTION = ComplianceRuleSpec(
    name="sec99_31_disclosure_exception",
    description=(
        "34 CFR 99.31(a) — an educational agency or institution may "
        "disclose PII from an education record without consent if the "
        "disclosure meets one of the listed exceptions. Callers relying "
        "on an exception must name which."
    ),
    tags=frozenset({"ferpa_exception_disclosure"}),
    checks=(
        MetadataCheck(
            metadata_key="sec99_31_basis",
            allowed_values=frozenset(
                {
                    # § 99.31(a)(1)–(16) and § 99.36 health/safety.
                    "school_official_legitimate_interest",
                    "other_school_enrollment",
                    "audit_evaluation_authorized_rep",
                    "financial_aid",
                    "state_local_authority_juvenile_justice",
                    "organizations_conducting_studies",
                    "accrediting_organizations",
                    "parent_dependent_student",
                    "judicial_order_subpoena",
                    "health_safety_emergency",
                    "directory_information",
                    "parent_violation_drug_alcohol",
                    "victim_of_crime",
                    "disciplinary_proceeding_result",
                    "sex_offender_registration",
                    "state_local_authority_state_law",
                }
            ),
        ),
    ),
    deny_message=(
        "FERPA 34 CFR 99.31(a): Consent-exempt disclosure requires a "
        "sec99_31_basis matching one of the 16 stated exceptions."
    ),
    citation=_cite("34 CFR 99.31(a)"),
)


_SEC_99_31_SCHOOL_OFFICIAL = ComplianceRuleSpec(
    name="sec99_31_school_official_role",
    description=(
        "34 CFR 99.31(a)(1) — disclosure to other school officials is "
        "permitted only when each has been determined to have "
        "legitimate educational interests. Callers using this basis "
        "must state the official_role and the legitimate_interest."
    ),
    tags=frozenset({"ferpa_school_official_disclosure"}),
    checks=(
        MetadataCheck(
            metadata_key="official_role",
            allowed_values=frozenset(
                {
                    "teacher",
                    "administrator",
                    "counselor",
                    "registrar",
                    "security_personnel",
                    "contracted_service_provider",
                    "data_steward",
                }
            ),
        ),
        MetadataCheck(metadata_key="legitimate_interest"),
    ),
    deny_message=(
        "FERPA 34 CFR 99.31(a)(1): School-official disclosure requires "
        "a permitted official_role and a stated legitimate_interest."
    ),
    citation=_cite("34 CFR 99.31(a)(1)"),
)


# ── § 99.37 — directory information ────────────────────────────────


_SEC_99_37_DIRECTORY = ComplianceRuleSpec(
    name="sec99_37_directory_optout_check",
    description=(
        "34 CFR 99.37 — an educational agency or institution may "
        "disclose directory information only if it has given public "
        "notice and the parent or eligible student has not opted out. "
        "Directory-info releases must verify the opt-out state."
    ),
    tags=frozenset({"ferpa_directory_information"}),
    checks=(
        MetadataCheck(
            metadata_key="directory_opt_out_state",
            allowed_values=frozenset({"not_opted_out", "notice_waived"}),
        ),
    ),
    deny_message=(
        "FERPA 34 CFR 99.37: Directory-information release requires "
        "directory_opt_out_state=not_opted_out."
    ),
    citation=_cite("34 CFR 99.37"),
)


# ── § 99.31(a)(9) — judicial orders / subpoenas ────────────────────


_SEC_99_31_9_JUDICIAL = ComplianceRuleSpec(
    name="sec99_31_9_judicial_notice",
    description=(
        "34 CFR 99.31(a)(9)(ii) — before disclosing records in "
        "compliance with a judicial order or subpoena, the school must "
        "make a reasonable effort to notify the parent or eligible "
        "student, unless the court order forbids disclosure of the "
        "order itself."
    ),
    tags=frozenset({"ferpa_judicial_disclosure"}),
    checks=(
        MetadataCheck(
            metadata_key="subject_notified",
            allowed_values=frozenset(
                {"yes", "notice_forbidden_by_order"}
            ),
        ),
    ),
    deny_message=(
        "FERPA 34 CFR 99.31(a)(9)(ii): Judicial disclosure requires "
        "subject_notified=yes, or =notice_forbidden_by_order when the "
        "court has expressly forbidden notice."
    ),
    citation=_cite("34 CFR 99.31(a)(9)(ii)"),
)


# ── § 99.35 — authorized representatives for audits ────────────────


_SEC_99_35_AUDIT = ComplianceRuleSpec(
    name="sec99_35_audit_representative",
    description=(
        "34 CFR 99.35 — disclosures to authorized representatives "
        "under § 99.31(a)(3) must be in connection with an audit, "
        "evaluation, or enforcement of education programs, with a "
        "written agreement specifying the scope of the study."
    ),
    tags=frozenset({"ferpa_audit_disclosure", "authorized_rep_study"}),
    checks=(
        MetadataCheck(metadata_key="study_agreement_id"),
    ),
    deny_message=(
        "FERPA 34 CFR 99.35: Disclosure to an authorized "
        "representative requires a study_agreement_id."
    ),
    citation=_cite("34 CFR 99.35"),
)


# ── § 99.32 — recordkeeping obligations ────────────────────────────


_SEC_99_32_RECORDKEEPING = ComplianceRuleSpec(
    name="sec99_32_disclosure_record",
    description=(
        "34 CFR 99.32(a)(1) — an educational agency or institution must "
        "maintain a record of each request for access to and each "
        "disclosure of PII from the education records of each student. "
        "Disclosure tools must emit a disclosure_record_id for the log."
    ),
    tags=frozenset({"ferpa_pii_disclosure"}),
    checks=(
        MetadataCheck(metadata_key="disclosure_record_id"),
    ),
    deny_message=(
        "FERPA 34 CFR 99.32(a)(1): PII disclosure requires a "
        "disclosure_record_id for the recordkeeping log."
    ),
    citation=_cite("34 CFR 99.32(a)(1)"),
)


def build_ferpa_policy(
    *,
    policy_id: str = "ferpa-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the FERPA enforceable-at-tool-boundary rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _SEC_99_10_INSPECT,
            _SEC_99_30_CONSENT,
            _SEC_99_31_EXCEPTION,
            _SEC_99_31_SCHOOL_OFFICIAL,
            _SEC_99_37_DIRECTORY,
            _SEC_99_31_9_JUDICIAL,
            _SEC_99_35_AUDIT,
            _SEC_99_32_RECORDKEEPING,
        ],
        framework="FERPA",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_ferpa_policy"]

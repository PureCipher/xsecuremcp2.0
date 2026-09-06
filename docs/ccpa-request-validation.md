# CCPA/CPRA Request Validation — pack 2.0.0

Reviewed September 6, 2026 against the [CCPA statute](https://cppa.ca.gov/pdf/20260101_ccpa_statute.pdf) and [California regulations effective January 1, 2026](https://cppa.ca.gov/regulations/pdf/ccpa_statute_eff_20260101.pdf).

## Request controls

This pack evaluates MCP requests before execution. It checks exact actor/action/resource grants, server/tenant scope, trusted issuer, request digest, expiry and session/device/risk posture. Missing evidence denies; client metadata and component tags cannot supply evidence or bypass checks.

The implementation combines purpose/minimization, data scope, recipient restrictions, retention, consumer preferences, sensitive use, age-specific sale/sharing consent and verified authority for consumer access/correction/deletion. Every consumer in a batch must pass. GPC or an active sale/sharing opt-out blocks sale/sharing even if another consent fact exists. Consumer access additionally requires exclusion of restricted identifiers. These controls map to §§7002, 7012, 7022–7028, 7050–7071 and 7080; applicable risk-assessment evidence maps to §§7150–7157.

## Evidence adapter contract

Configure `ccpa_evidence_resolver` on `PolicyEnforcementMiddleware`. It returns `CcpaEvidence` and a tuple of `CcpaConsumer` entries, or `None`. Use authoritative server-side records, never a deserialized client assertion. A resolver exception denies the request.

The resolver must:

- Resolve the full affected record/field and consumer set from actual tool arguments, resource URI or prompt arguments. Reject incomplete/unknown batches. `complete_consumer_and_field_scope_verified` attests to that complete set, not just IDs supplied by the caller.
- Bind evidence to the authenticated actor, exact operation resource/action, server/tenant scope and canonical request metadata digest. Each invocation needs fresh verification; do not refresh old preference evidence merely by changing its timestamp.
- Read current preference/revocation/deletion status and age eligibility from authoritative systems. Unknown booleans are rejected. For minors, attest to the appropriate specific sale/sharing opt-in, not general terms acceptance.
- Verify purpose compatibility or specific informed consent, applicable notices, contracts, processor reuse/combination restrictions, recipient authority, proportionality and applicable risk-assessment requirements. Do not equate a role name with these facts.
- Verify that the server enforces the attested field filtering, prohibited-identifier exclusion and output security. This evaluator does not inspect response payloads or perform redaction. Changes to selected records between evaluation and execution must trigger reevaluation or be prevented by the server.

Use the field names in `CcpaEvidence`/`CcpaConsumer` as the adapter contract. Facts are immutable sets. Evidence is transient; grants, trusted issuer, scope and policy version persist through normal policy serialization. Catalog staging preserves the source references. No automatic migration or activation occurs.

## Deliberate limits

This is not business-wide certification. Consumer-rights case management, notice delivery, contract creation, audits and regulatory submissions remain external. The resolver verifies relevant outcomes; the registry does not implement those workflows.

ADMT requests are denied pending a dedicated assessment policy, including before the Article 11 compliance date of January 1, 2027. That is a conservative product restriction, not a claim that every AI call is prohibited by the statute. `uses_admt` must reflect the applicable definition, not merely the presence of an LLM.

This version does not implement legal-exemption overrides, opt-in overriding a currently active GPC/opt-out, or retained-data exception processing during a deletion restriction. Configure authoritative preferences after valid external changes; never bypass a restriction with a generic consent flag. Separate Delete Act/DROP obligations and organization-wide audit programs are outside this pack.

Empty catalog grants/issuer/scope intentionally deny execution. Configure and validate a trusted adapter in staging before activation.

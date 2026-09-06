# HIPAA Request Validation — pack 2.0.0

Reviewed September 6, 2026 against [HHS's Privacy Rule summary](https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html), [45 CFR Part 164](https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164), and [HHS's reproductive-health rule status](https://www.hhs.gov/hipaa/for-professionals/special-topics/reproductive-health/final-rule-fact-sheet/index.html). The eCFR displayed Title 45 current through September 3, 2026 during review. Court orders and applicable additional law must be assessed by the trusted verifier.

## Request model

The old catalog accepted an actor-role label plus any stated purpose, depended on tags and applied a global business-hours gate. Version 2 requires exact actor/action/resource grants and current patient-specific evidence. It evaluates every patient and every declared effect; untagged components cannot bypass it. Ordinary authorized requests are not subject to a hardcoded time window.

Configure `hipaa_evidence_resolver` on `PolicyEnforcementMiddleware`. Return immutable `HipaaEvidence` and `HipaaPatient` objects based on authoritative records. Missing evidence, unknown classifications and resolver failures deny execution. Never deserialize trusted evidence from client arguments or role metadata.

The resolver must bind evidence to the authenticated actor, server/tenant scope, action, resource, complete request digest, verification time and expiry. It must establish the actual patient/record/field scope, all effects, purpose and recipient. This includes every patient in batch results and applicable representative/minor authority. Do not treat a grant to call a tool as permission to see all of its data.

## Conditions evaluated

The pack supports explicit grounds for treatment, payment, operations, individual access, authorization, directory/care involvement, the twelve §164.512 categories, limited data sets, HHS enforcement and administrative simplification. Each ground requires its own verified conditions for each patient. These facts attest to the full applicable conditions; selecting a ground name does not establish them.

Minimum-necessary scope is required unless an explicitly classified, verified exception matches every patient's ground. The treatment exception only supports provider requests/disclosures and cannot exempt a combined internal-use operation. Security and request-scope checks remain required under all exceptions.

Marketing, sale and psychotherapy-note handling require current authorization and their additional scope conditions in this version. Applicable patient restrictions deny. Business-associate actors and recipients require separate agreement/scope evidence. Exchanges, storage, updates and disposal each add their own safeguards.

## Verifier responsibilities

Validate legal grounds, authorization completeness/expiry/revocation, permissible conditioning and any remuneration statements, current restrictions, minimum-necessary scope, recipient identity/authority, agreement/instruction scope, security, and accounting requirements for the actual request. `request_restricted` must reflect restrictions applicable to this precise operation, including applicable self-paid health-plan restrictions; it is not merely a flag that a patient once requested a restriction.

For §164.512 grounds, verify the applicable subsection conditions, legal process, recipient authority, required notices or assurances, and limits. For limited data sets verify excluded identifiers, permitted purpose and data-use agreement. For individual disclosures verify representative authority and the applicable access scope. Broad consent or a claimed professional role is insufficient.

The server must enforce attested output filtering, transmission/storage protections, mutation authority and audit/accounting controls. This policy does not redact responses, create agreements, collect authorizations, process access requests or perform those external workflows. Prevent authorization/scope changes before execution or reevaluate.

## Boundaries and current rule status

This is request admission, not organization-wide HIPAA certification or a complete Security/Breach Notification Rule implementation. State law, 42 CFR Part 2 and other applicable restrictions are not overridden. Part 2 records are blocked pending a dedicated additional policy, including mixed PHI/Part 2 requests.

Exceptions allowing psychotherapy notes, marketing or sale without authorization are not implemented. Restriction overrides and emergency exceptions are also unsupported; this conservative behavior can deny otherwise lawful requests. De-identified-data and incidental-disclosure routes are not implemented. Assess those through separate policies rather than relabeling PHI.

HHS reports that most provisions of the 2024 reproductive-health rule were vacated on June 18, 2025. This pack does not impose the vacated blanket attestation requirement. The verifier must assess currently applicable law and court orders; the presence of text on eCFR alone is insufficient to determine enforceability.

## Persistence

Exact grants, trusted issuers, server scope, evidence age and version serialize through the existing policy store. Catalog staging retains version/source metadata. Request evidence is transient and is not saved as policy configuration.

The catalog ships with empty grants/issuers/scope and denies until configured. Validate a real trusted resolver in staging before activation. Publishing this catalog update does not replace active policies. The legacy `hipaa` metadata provider remains distinct for compatibility.

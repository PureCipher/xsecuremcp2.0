# GDPR Request Validation — pack 2.0.0

Source: [Regulation (EU) 2016/679, consolidated text 2016-05-04](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504). Reviewed September 6, 2026. National law and applicable regulatory decisions must be assessed externally.

## What changed

The previous catalog pack accepted a client metadata legal-basis label and depended on component tags. This version requires exact actor/action/resource grants plus current server-verified evidence for every affected subject. Missing evidence denies, including on untagged components. It combines all declared operation effects and data categories; an export cannot bypass disclosure checks by also declaring a read.

## Evidence contract

Configure `gdpr_evidence_resolver` on `PolicyEnforcementMiddleware`. Return immutable `GdprEvidence`/`GdprSubject` objects after consulting authoritative systems. Never construct these objects from unverified client claims. A resolver failure denies the request.

Bind evidence to the actual actor, action, resource, canonical request metadata digest and server/tenant scope. The resolver must establish the complete affected subject/record/field set, actual processing purpose, all operation effects, recipient relationship and international access/transfer path. It must verify that the actor is authorized for that complete data scope. It must not omit restricted subjects from batch evidence or classify pseudonymized data as anonymous.

Each subject carries one applicable legal basis and its corresponding verified conditions. For mixed purposes requiring different bases, split processing into separately evaluated requests. Basis verification includes necessity and applicable law, not simply a basis name. Consent verification includes specificity, freedom, information, demonstrability, current status and applicable child/jurisdiction authority. A new label must not be used to evade withdrawn consent.

Special-category data needs both an Article 6 basis and verified conditions for the selected Article 9 ground. The ground-specific fact attests to all relevant limits, safeguards and national-law requirements; it is not a substitute for that assessment. Criminal-offence data requires separate authority. Transfer evidence must establish current mechanism validity, scope, destination, security and onward-transfer conditions, including applicable assessments. A contract title or country name alone is insufficient.

The resolver also verifies purpose compatibility, minimization, accuracy, retention, transparency, output security and applicable DPIA/prior-consultation outcomes. These are external evaluations; this policy does not deliver notices, conduct DPIAs, create contracts, redact output or run consumer-rights workflows. The server must enforce attested output/field constraints and prevent scope or authorization changes between evaluation and execution, or reevaluate.

## Supported decisions and limits

The pack checks six Article 6 grounds, ten Article 9 grounds, Article 10 authority, current objections/restrictions, recipient arrangements and Chapter V transfer evidence. Significant solely automated decisions are blocked pending a dedicated Article 22 implementation. Generic use of an LLM does not automatically make a request an Article 22 decision; the trusted resolver determines applicability.

A marketing objection blocks direct marketing. Processing objections under public-task/legitimate-interest grounds and active processing restrictions are conservatively blocked; their exceptions are not implemented. Verified deletion may proceed under a separately valid legal basis and erasure scope. Storage under a restriction, statutory overrides and rights-balancing exceptions require a future extension. These are product restrictions, not claims that every blocked request is unlawful.

Data-subject delivery requires verified request authority and protection of others' rights. This is not a complete access/portability workflow or an automatic Article 20 eligibility determination. A rights-related operation still needs a valid legal basis and verified scope.

This pack provides request safeguards, not full GDPR compliance or organizational certification. Institutional accountability, records, supervisory procedures, breach handling and national-law exceptions remain external.

## Persistence and activation

Grants, issuer allowlist, scope, evidence age and version persist through policy serialization. Catalog staging retains source/version metadata. Trusted request evidence is transient and is not stored as policy configuration.

Empty catalog grants/issuer/scope deny execution until configured. Validate the resolver in staging before activation. Existing active policies are not migrated or replaced automatically; the legacy metadata-based `gdpr` provider remains available for compatibility and is distinct from the new `gdpr_request` catalog provider.

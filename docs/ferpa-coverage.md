# FERPA request-validation coverage

Pack **2.0.0** implements request authorization, not institutional workflows.
Reference: **20 U.S.C. 1232g; 34 CFR Part 99**. Sources reviewed **2026-09-06**:
[Department of Education](https://studentprivacy.ed.gov/ferpa) and
[eCFR](https://www.ecfr.gov/current/title-34/subtitle-A/part-99).

## Request decision

The `ferpa_request` provider evaluates consent, each of the sixteen 99.31(a)
exceptions, and de-identified releases. A directory exception cannot authorize
other education records. Authorities are alternatives, not unrelated AND rules.
Every applicable condition within the selected authority must be verified.
`FERPA_BASES` in `policies/ferpa_request.py` is the executable condition map.

Execution without trusted evidence is denied, including untagged operations.
Client metadata cannot provide evidence. The verifier must return a `FerpaEvidence`
object through `PolicyEnforcementMiddleware(ferpa_evidence_resolver=...)`.

Evidence binds the authenticated actor, action, resource, complete request-metadata
digest and an explicit server/tenant scope. It carries subject, recipient, purpose,
classification, selected authority, verified facts, issue/expiry times and issuer.
Unknown authority/classification, scope mismatch, expired or stale evidence,
untrusted issuer, changed arguments and absent required facts deny access.
The verifier is called afresh on each execution; resolver errors deny access.
Evidence is not serialized into policy configuration or accepted from simulation JSON.

## External evidence contract

The adapter MUST authenticate its external source, verify current revocation and
rights state, match actual requested records/fields and recipients, and populate
only facts it verified. It must not copy MCP arguments into `facts`. An issuer name
alone is not cryptographic authentication; the adapter authenticates its transport
and verifies the source's signatures/credentials before constructing evidence.
Use a unique `scope_id` per institution and server boundary.

Common conditions cover identity, subject/record/recipient/purpose scope, current
authority, applicable recordkeeping, redisclosure and contested-statement limits.
Where a duty has statutory exclusions, its verified condition means the applicable
requirements or exclusion were checked, not that a workflow was created here.
De-identification uses its own conditions and does not require identifying subjects.
Verified record exclusions defer to other applicable policies.

This validates externally established facts. It does not prove that an upstream
institution supplied truthful evidence, determine every legal fact automatically,
or inspect/filter a tool's returned payload. Servers must enforce the authorized
record/field scope during execution. Do not describe this as institution-wide
FERPA certification or activate it without a trusted adapter.

## Configuration and persistence

```json
{
  "type": "ferpa_request",
  "policy_id": "ferpa-request-validation",
  "version": "2.0.0",
  "scope_id": "institution-1/server-1",
  "trusted_issuers": ["institution-evidence-service"],
  "max_evidence_age_seconds": 60
}
```

Empty issuer/scope settings in the starter intentionally deny execution. Evidence
age is configurable from 1 to 300 seconds. Use shorter windows where appropriate;
the verifier must still check current authorization on every invocation.
Configuration is declarative and survives policy snapshot serialization/restoration.
Saved packs and proposals use the configured persistent storage backend. Institutional
evidence stays with its external authority. Deployment does not migrate active chains.

## Regulatory scope

| References | Request-validation treatment |
| --- | --- |
| 99.1–99.3, 99.8 | Trusted applicability, classification and record-exclusion assessment |
| 99.4–99.5, 99.10–99.12 | Verified rights holder and permitted inspection scope |
| 99.7, 99.37 | Applicable notice/opt-out conditions for disclosure; no notice management |
| 99.20–99.22 | Statement conditions where records are disclosed; no hearing/amendment workflow |
| 99.30 | Signed, dated, rights-holder consent matching the requested disclosure |
| 99.31(a)(1)–(16) | Individual authority paths with required verified conditions |
| 99.31(b)–(c) | De-identification/research-code conditions and recipient identity |
| 99.32–99.33 | Applicable disclosure-record and onward-disclosure conditions |
| 99.34–99.35 | Transfer/audit scope, notice/agreement/use/destruction conditions |
| 99.36 | Significant threat, recipient necessity and emergency scope |
| 99.38–99.39, Appendix A | Applicable juvenile-justice and disciplinary-result conditions |
| 99.6 | Reserved |
| 99.60–99.67 | External institutional/agency enforcement; no product workflow |

Tests cover every authority path and missing branch condition, cross-scope and
actor mismatches, stale/expired evidence, request mutation, missing authority,
serialization, database proposal reload and resolver failures.

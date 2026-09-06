# SOC 2 Request Validation — pack 2.0.0

Reviewed September 6, 2026. Framework: AICPA 2017 Trust Services Criteria. [AICPA's current resource listing](https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022) identifies revised points of focus from 2022. The [public AICPA criteria text](https://assets.ctfassets.net/rb9cdnjh59cm/72xv4p67HVXKp6CjWmjkPk/1cdbfa19f6307e2720396b66a6194dc9/trust-services-criteria-updated-copyright.pdf) used for the criterion mapping includes March 2020 updates; this implementation does not claim an exhaustive review of the 2022 points of focus.

## Scope

This is a request-admission policy aligned to selected controls in the security, availability, processing integrity, confidentiality and privacy categories. It is not a SOC 2 report, certification, or comprehensive assessment of an organization's controls.

The earlier catalog pack combined broad wildcard access, role names and a global weekday gate. Version 2 requires exact grants and trusted request evidence. It evaluates all declared effects together. Ordinary reads remain available outside change windows; configuration/deployment requires verified change authorization. Existing active policies are not automatically replaced.

## Implementation and adapter contract

Supply `soc2_evidence_resolver` to `PolicyEnforcementMiddleware`. Return `Soc2Evidence` from authoritative server-side systems. Never deserialize it from tool arguments, client metadata or component tags. Missing evidence and resolver failures deny execution.

The resolver must classify the complete request, including hidden side effects and every selected record/field. Its `effects` set may include read, process, write, delete, export, configure and deploy. A read/export operation must include both effects. Unknown effects or data classification deny. Bind the evidence to actor, action, resource, server/tenant scope and the canonical request metadata digest, with current verification and expiry timestamps.

The evaluator's concrete safeguards are:

- Exact access grants, current session/device/risk evidence, verified least privilege and full data scope.
- Available audit capture, clear incident-admission status, and a reserved request capacity budget.
- Verified input, processing and output-delivery controls.
- Confidential data access/output protection and personal-data purpose, current privacy choices and subject/field scope.
- Authorized, protected exports; verified third-party risk/contracts where applicable.
- Verified mutation scope and recovery controls for write/delete/configure/deploy. Disposal requires verified method/scope. Deletion alone may proceed after retention expires; combined read/delete still needs a permitted-use basis.
- Independently authorized system changes, approved scope, verified execution window and validation. The approver must differ from the authenticated actor; the resolver must also verify the approver's real authority and independence, including the underlying human identity when service accounts act on someone's behalf.

A fact means the adapter has checked an actual control for this request. A generic `verified=true`, caller role, or record of an old audit is insufficient. The evaluator does not implement queues, approvals, auditing workflows, output redaction, capacity reservations or recovery operations itself. Those are external capabilities whose relevant state is verified before admission. Keep state stable through execution or reevaluate when scope, preferences or authorization changes.

## Persistence and activation

The policy's version, exact grants, issuer allowlist, scope and evidence-age limit round-trip through normal policy configuration serialization. Staged catalog proposals retain the version and source references. Request evidence is transient and is not saved as policy configuration.

The shipped catalog uses empty grants/issuers/scope and denies execution until configured. Prepare an authenticated adapter and validate it in staging before activation. The catalog rate limit is only an additional local throttle; it does not establish availability guarantees.

## Coverage boundaries

Organizational governance, personnel controls, physical security, audit opinions, historical operating effectiveness and comprehensive trust-service assessments remain external. The criterion references identify alignment, not proof that the criteria are fully satisfied. Privacy safeguards here do not replace the applicable FERPA, CCPA/CPRA, HIPAA or other legal policy pack. Compose the relevant policies when their obligations also apply.

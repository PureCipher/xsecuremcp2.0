# Policy pack hardening

## Acceptance criteria for every pack

A pack must describe its actual scope, identify trusted input dependencies, and
include positive and negative tests. The matrix covers classified/unclassified
resources, missing evidence, mismatched subjects and tenants, mixed rule matches,
read/write operations, role compatibility, revocation, time boundaries, persistence,
and recovery. Requirements implemented elsewhere must identify the enforcing
component; metadata assertions alone do not prove a legal basis or consent.

The existing `compliance_packs` library has richer rules than the catalog starters.
Review those rules before reuse. Do not duplicate them or assume that their presence
means they are enforced by a production request path.

| Pack | Required coverage work | Status |
| --- | --- | --- |
| FERPA | Non-bypassable mixed classifications; inspection, disclosure, audit and judicial prerequisites; trusted disclosure/subject evidence; classification coverage | Composition fixed and four workflow rules reused; evidence integration remains |
| Zero Trust | Explicit resource/client grants, trusted verification, administrative recovery, revocation | Pending |
| Published Tools Only | Trusted published-state enforcement; distinguish read-only from mutating calls | Pending |
| Strict Change Control | Action-scoped schedules, runtime role compatibility, separation of duties | Pending |
| Balanced Registry | Least-privilege tool actions and explicit dependencies on lifecycle/profile gates | Pending |
| GDPR | Trusted legal basis, special categories, purpose/subject scope, minimization, retention/rights/transfer dependencies | Pending |
| HIPAA | Minimum-necessary resource scope, trusted role/purpose, administrative schedule scope, emergency access and audit dependencies | Pending |
| SOC 2 | Action-scoped change windows, role separation, evidence/control ownership and operational dependencies | Pending |
| PCI DSS | Operation-specific CHD/SAD rules, masking/storage/retention dependencies, trusted roles | Pending |
| CCPA/CPRA | Subject-specific opt-out/GPC evidence, purpose+sharing composition, revocation and rights workflows | Pending |

## Iteration 1: FERPA

The catalog pack now requires every matching rule to pass. A directory classification
cannot override failed student-record checks, and a passing educational-interest
check cannot override a failed directory opt-out check. This is a conservative
intersection policy, not a complete model of every permitted FERPA disclosure.

Four existing rules are reused from the FERPA compliance library:

- Inspection workflow: requires an inspection request identifier.
- PII disclosure workflow: requires a disclosure record identifier.
- Audit disclosure: requires a study agreement identifier.
- Judicial disclosure: requires notice status, including the existing order-forbids-notice value.

These are tagged workflow prerequisites. They do not fetch or validate the referenced
records, determine whether a judicial order is valid, or classify data automatically.
Untagged resources still defer from the compliance provider; other providers can allow
them. Trusted classification and evidence validation remain required work.

The core provider is versioned 1.1.0. Saved snapshots and active chains are not silently
rewritten: operators must create, simulate, and review a new proposal before applying.
The shared serializer and declarative loader now preserve rule citations so reused
rules retain their source references after persistence and reload.

## Iteration 2: FERPA workflow expansion

The catalog is now version 1.2.0 with 24 prerequisites, including 18 additional
workflow rules. See [the section coverage register](ferpa-coverage.md) for all
remaining requirements and runtime limitations. The earlier iteration notes above
describe version 1.1.0 and are retained as history.

## Scope correction: FERPA 2.0.0

The product validates requests; it does not manage institutional workflows.
Version 2.0.0 replaces the 24 prerequisite catalog with a dedicated request
validator, authority alternatives and a trusted evidence adapter boundary.
The earlier iteration notes are historical and do not describe the current pack.
See [FERPA request validation](ferpa-coverage.md) for configuration and limitations.

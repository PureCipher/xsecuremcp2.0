# Balanced Registry Guardrails — product policy v2.0.0

This pack is an access baseline. It reuses `ZeroTrustPolicy` rather than duplicating the evaluator. Configuration: exact actor/resource/action grants, trusted issuers, server/tenant scope and evidence-age limit, followed by a 250-request/hour local throttle.

The old catalog supplied wildcard tool patterns and role mappings, including reviewer policy-management access. The revised pack grants nothing by default. Configure each intended capability explicitly. Client role claims cannot add permissions, and a tool grant does not imply an administrative grant.

Runtime verification uses `zero_trust_evidence_resolver`. Identity, scope, full request digest, freshness, session, device and risk must all pass. Its adapter contract is the same as the Zero Trust pack. A deployment without an adapter or valid grants denies access if activated.

This baseline does not assert publication status, read-only behavior, regulatory data authority or approval state. Compose Published Tools Only or the relevant data policy where required. It does not implement organizational workflows. Registry endpoint authorization remains independently required.

Policy configuration persists through the existing serializer; staged proposals retain catalog version/source metadata. Existing active policies are not migrated or replaced automatically. Version 2.0.0 is a PureCipher product policy, not a new regulatory standard.

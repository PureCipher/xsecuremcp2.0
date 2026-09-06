# Zero Trust request validation

Pack version **2.0.0**. Source: [NIST SP 800-207](https://doi.org/10.6028/NIST.SP.800-207),
August 2020, reviewed September 6, 2026. This is request authorization, not a claim
that the product implements an entire Zero Trust architecture.

## Configuration

```json
{
  "type": "zero_trust",
  "version": "2.0.0",
  "scope_id": "tenant-1/server-1",
  "trusted_issuers": ["posture-service"],
  "max_evidence_age_seconds": 60,
  "grants": [
    {"actor_id": "authenticated-client-id", "resource_id": "student-search", "actions": ["call_tool"]}
  ]
}
```

Match actual MCP component identifiers, not invented `tool:` prefixes. Grants are
exact actor/resource/action tuples; wildcard patterns and implicit role grants are
not accepted. Add explicit discovery and administrative recovery grants where
needed. Empty configuration denies access. Simulate and review before activation.

Supply `zero_trust_evidence_resolver` to `PolicyEnforcementMiddleware`. The resolver
must authenticate its posture/identity source and return `ZeroTrustEvidence` for
the specific request. Issuer names are not authentication by themselves. Never
construct trusted evidence directly from MCP arguments or a `verified` metadata
flag. The adapter must check current session revocation, device/workload posture
and risk on every request.

Evidence binds actor, action, resource, server/tenant scope and request digest.
Changed arguments, mismatched scopes, stale/future/expired evidence and unavailable
resolvers deny execution. Middleware invokes the resolver on each evaluation.
Discovery uses the authenticated principal and explicit grants too.

The policy configuration round-trips through the existing saved policy/versioning
mechanism. Evidence is external and short-lived, not copied into saved policy JSON.
Updating the catalog does not mutate existing active policies or saved revisions.
The new pack replaces the prior broad `tool:` prefix and untrusted metadata check.

## Boundaries

The adapter establishes facts; the policy checks them and the exact grant.
This does not implement device enrollment, posture scanning, network segmentation,
continuous connection termination, output inspection, or institutional workflows.
The starter retains its separate limit of 50 requests per actor per 1,800 seconds.
Those counters are process-local; deployment-wide limiting needs shared enforcement.
Long-running calls need their own revocation/cancellation handling after initial
admission. Keep scopes and authenticated actor identities stable and unique.

Tests cover exact grants, forged role/verification flags, request/tenant mismatches,
posture failures, freshness, configuration reload and resolver outages.

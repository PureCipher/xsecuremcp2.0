# Strict Change Control v2.0.0

PureCipher product policy, reviewed September 6, 2026. This pack validates individual MCP and registry requests; it does not create approval workflows or claim regulatory certification.

The catalog combines `strict_change` with a rate limit. Exact actor/resource/action grants, trusted issuers and a server/tenant scope must be configured. Empty grants deny requests. Configuration round-trips through the existing policy serialization and storage layer. Catalog staging does not activate the pack.

A server-owned `change_evidence_resolver` supplies `ChangeEvidence` from authoritative systems. All evidence is bound to the authenticated actor, action, resource and canonical request metadata digest, with current session/device/risk posture. The resolver must classify **all** effects and targets, including indirect writes, and verify audit capture availability. Client roles, tool hints and approval flags cannot supply these facts.

Read/compute requests require exact access and current evidence, but no change window. Writes, deletes, configuration and deployment require an identified, non-revoked approval covering the exact request, an independently authorized approver distinct from both actor and requester, valid approval dates, and an open execution window. Registry submission, review and policy-management actions always require change approval even if classified as reads. Unknown actions/effects deny.

Required change facts attest approver authority, separation of duties, approved scope, validation and recovery controls. Time intervals include their start and exclude their end. Missing, stale, mismatched or unavailable evidence denies access.

External adapters must resolve identities consistently, establish requester authority, check revocation and verify these facts using trusted records. This evaluator does not implement approval creation, rollback execution, continuous enforcement, or atomic one-use approval consumption. Deployments requiring one-use approvals must enforce consumption and replay protection at execution. The adapter must also prevent changes between evidence verification and execution. Policy configuration alone does not establish runtime enforcement: install the provider and resolver on every protected route.

Source: `fastmcp_slim/fastmcp/server/security/policy/policies/strict_change.py`; catalog: `workbench.py`; runtime callback: `middleware/policy_enforcement.py`. Rules are product-owned and versioned in Git.

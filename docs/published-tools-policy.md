# Published Tools Only — product policy v2.0.0

This is a PureCipher catalog safeguard, not a regulatory compliance pack. Source: the `published_tools` provider in this repository. Reviewed September 6, 2026.

## Change

The old pack allowed the `tool:*` resource pattern without verifying publication state. Its read-only description was also not enforced. Version 2 checks current publication, revocation, signature validity, manifest identity and exact component binding, plus read-only effects. It permits only `list_tools` and `call_tool`; resources, prompts and registry administrative actions are outside this pack.

A tool must have an exact actor/resource/action grant and current trusted evidence. Discovery is evaluated per component and filters out tools that would not satisfy this pack. The permitted effect set contains only `read` and/or `compute`; an unknown, mixed read/write, or empty classification denies. Read-only tool access does not authorize sensitive-data disclosure: compose the applicable data policy separately.

## Trusted resolver

Configure `published_tool_evidence_resolver` on `PolicyEnforcementMiddleware`. It must load authoritative listing status and revocation state, verify the signed manifest with an approved publisher key, and establish the exact binding between listing ID/version, manifest digest, deployed component and requested resource. A syntactically valid digest is not evidence that verification occurred.

Bind the returned `PublishedToolEvidence` to actor, action, resource, request digest and tenant/server scope. The resolver must examine the actual version that will execute and the request's possible effects. Client-provided `published` tags, `readOnlyHint`, arbitrary manifest URLs or self-reported signatures are insufficient. Review or enforce effects at the server/sandbox boundary; this policy does not inspect executable code or enforce an operating-system sandbox.

The server must prevent version swaps or authorization changes between verification and execution, or re-evaluate. Use fresh authoritative revocation state. Do not extend a cached verification's lifetime by rewriting its timestamp. Resolver failures or missing results deny execution.

## Persistence and release

The normal policy store persists grants, trusted issuers, scope, version and evidence-age configuration. Catalog staging retains version and source metadata. Evidence is transient. Empty grants/issuers/scope deny execution until an operator configures and tests the resolver. Publishing the pack does not automatically activate it or alter active policy chains.

The product-policy source link points to the repository; this pack does not claim an external legal standard. Its checks do not replace user/profile permissions, data consent, or the other SecureMCP control planes.

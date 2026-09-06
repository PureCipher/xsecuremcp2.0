# PCI DSS request validation

Pack version **2.0.0**; standard reference **PCI DSS v4.0.1, June 2024**.
Reviewed September 6, 2026 against the [PCI SSC document library](https://www.pcisecuritystandards.org/document_library/),
[SAD guidance](https://www.pcisecuritystandards.org/faqs/1154/),
[PAN display guidance](https://www.pcisecuritystandards.org/faqs/1492/), and
[stored PAN guidance](https://www.pcisecuritystandards.org/faqs/1222/).

## Runtime behavior

`pci_request` reuses exact actor/resource/action grants and fresh server/tenant-bound
posture validation. Client role, justification and `verified` strings cannot confer
access. Configure `pci_evidence_resolver` on `PolicyEnforcementMiddleware` to obtain
`PciEvidence` from an authenticated external verifier on every request.

The evidence describes the actual requested data elements, operation, payment
authorization stage, PAN presentation and protected handling. The verifier must
map the actual MCP operation and complete requested scope to these values; callers
must not select their own trusted evidence. Argument changes invalidate the digest.
Empty configuration denies access. Explicitly authorized component discovery does
not run account-data handling checks because it is not a record-data operation.

| Request | Required safeguards |
| --- | --- |
| All executions | Exact grants, current trusted posture, verified business need, record/field scope, recipient and audit-data protection |
| PAN display | Verified masking, or separately verified documented full-PAN business need |
| PAN storage | Verified unreadable storage and permitted retention |
| Transmission | Strong cryptography and authenticated destination (conservative rule for all transports) |
| Pre-authorization SAD processing | Verified payment-authorization scope; no SAD exposure to the MCP client |
| Pre-authorization SAD storage | Additionally requires strong cryptography and approved retention |
| Post-authorization SAD | Denied for display, processing, transmission and storage |
| Deletion | Verified deletion scope and method; allows removal of post-authorization SAD |

The conservative pack does not support issuer-specific SAD retention exceptions.
It refuses SAD display/exposure to MCP clients at any authorization stage. Those
are product restrictions, not a statement that all such cases have identical
requirements under the standard. Data elements are evaluated together: including
PAN cannot exempt CVV, full track data, PIN or PIN blocks from SAD restrictions.

## Configuration

Use `type: pci_request`, explicit `grants`, `trusted_issuers`, `scope_id`, and
`max_evidence_age_seconds` (1–300). The grant schema matches the Zero Trust pack.
Serialization preserves this distinct PCI type through saved packs and version
restore. The starter retains 60 requests per actor per 1,800 seconds; rate counters
are process-local. Existing active packs are not silently migrated.

## Scope and dependencies

The provider evaluates requested operations. It does not mask returned bytes,
inspect actual encryption, erase storage, redact external logs or certify a cardholder
data environment. The trusted adapter and executing server must establish and
honor those protections. Evidence flags alone are not proof without that trust boundary.
Network security, secure configuration, malware defenses, software security, physical
security, testing and organizational controls remain outside this request policy.
The old global business-hours restriction is removed: it was not a universal PCI
requirement and incorrectly blocked authorized operations, including remediation.
The legacy `compliance_packs/pci_dss.py` factory remains separate from this catalog
pack; it is not the new runtime validator.

"""Capability-level policy bundles for the SecureMCP Policy Kernel.

Public API::

    from fastmcp.server.security.policy.capability import (
        default_capability_bundle,
        DEFAULT_REGO_MODULE,
        DEFAULT_CEDAR_POLICY,
    )

    providers = default_capability_bundle()  # [RegoPolicy, CedarPolicy]

The bundle encodes the seven capability rules the SecureMCP kernel
promises to enforce on any listing that opts in:

1. Deny-by-default across every action.
2. Destructive actions in production are blocked unless explicitly approved.
3. Backup deletion is always blocked.
4. Database / Kubernetes / IAM / cloud / deployment / DNS / firewall /
   credential changes require approval.
5. Production access is read-only for agents by default.
6. Every decision is audited (handled by PolicyAuditLog, not by these
   bundles directly).
7. Execution cannot bypass the Policy Kernel (handled by the
   PolicyEnforcementMiddleware wiring, not by these bundles).

The Rego module and Cedar policy are shipped side-by-side so we can
exercise both evaluators on every call and compare results during
rollout. In steady state they return matching decisions; a mismatch
surfaces as a diagnostic in the audit log (the Rego provider's reason
and the Cedar provider's reason land on the same PolicyResult chain).
"""

from fastmcp.server.security.policy.capability.bundle import (
    DEFAULT_CEDAR_POLICY,
    DEFAULT_REGO_MODULE,
    default_capability_bundle,
)

__all__ = [
    "DEFAULT_CEDAR_POLICY",
    "DEFAULT_REGO_MODULE",
    "default_capability_bundle",
]

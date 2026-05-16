"""Default capability bundle: Rego + Cedar expressing the kernel rules.

The two bundles are functionally equivalent; we ship both so the
policy kernel can evaluate an action through *both* engines on every
call. Running both isn't redundant — it's the no-bypass guarantee.
If one evaluator mis-parses or mis-evaluates a rule, the other still
denies. The PolicyEngine ANDs their outputs (DENY wins,
REQUIRE_APPROVAL beats ALLOW), so a disagreement fails safe toward
denial.

The rule set intentionally mirrors the brief verbatim so someone
reviewing the policies can match them back against the requirements
without decoding:

1. Deny-by-default — ``default allow = false`` + no blanket permit.
2. Destructive prod actions — DENY unless approved.
3. Backup deletion — hard DENY regardless of approval.
4. Sensitive-resource changes — REQUIRE_APPROVAL.
5. Prod read-only for agents — writes REQUIRE_APPROVAL.

The well-known destructive / sensitive action / resource labels are
hardcoded in both bundles because they are the *defaults*: operators
who want to extend or override them wire additional providers around
this bundle rather than editing this file.

Note on Rego formatting: every rule body expression is on a single
line, and multi-value sets are written inline rather than spread
across lines. The built-in Rego subset evaluates rule bodies
statement-by-line, so a multi-line set literal would split a rule
across parse boundaries. The rules below are still readable and
auditable, just denser.
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.cedar import CedarPolicy
from fastmcp.server.security.policy.policies.rego import RegoPolicy

# Destructive verbs and sensitive resource types used throughout the
# Rego module. Kept as module constants so the documentation and the
# policy stay in sync.
_DESTRUCTIVE_ACTIONS = (
    '"delete", "destroy", "drop", "truncate", "purge", '
    '"update", "patch", "upsert", "deploy", "rollback", '
    '"rotate", "revoke"'
)
_SENSITIVE_RESOURCE_TYPES = (
    '"database", "cluster", "iam_role", "cloud_resource", '
    '"deployment", "dns_record", "firewall_rule", "credential", "secret"'
)
_BACKUP_DESTRUCTIVE = (
    '"delete", "destroy", "drop", "purge", "wipe", "rm"'
)


DEFAULT_REGO_MODULE = f"""
package securemcp.capability

default allow = false

deny[msg] {{
    input.resource_type == "backup"
    msg := "Destructive action on a backup is never permitted"
}}

deny[msg] {{
    input.action == "delete_backup"
    msg := "delete_backup is never permitted by the default bundle"
}}

deny[msg] {{
    input.resource_type == "backup"
    input.action in {{{_BACKUP_DESTRUCTIVE}}}
    msg := sprintf("Backup deletion denied: action=%s resource=%s", [input.action, input.resource_id])
}}

require_approval[msg] {{
    input.environment == "production"
    input.action in {{{_DESTRUCTIVE_ACTIONS}}}
    input.resource_type in {{{_SENSITIVE_RESOURCE_TYPES}}}
    not input.approval_granted
    msg := sprintf("Production %s on %s requires approval", [input.action, input.resource_type])
}}

require_approval[msg] {{
    input.resource_type in {{{_SENSITIVE_RESOURCE_TYPES}}}
    input.action in {{"delete", "destroy", "drop", "create", "update", "patch"}}
    not input.approval_granted
    msg := sprintf("Sensitive-resource change on %s requires approval", [input.resource_type])
}}

require_approval[msg] {{
    input.environment == "production"
    input.principal_type == "agent"
    input.action in {{"write", "update", "patch", "delete", "destroy"}}
    not input.approval_granted
    msg := "Production write from an agent requires approval"
}}

allow {{
    input.environment == "production"
    input.principal_type == "agent"
    input.action in {{"call_tool", "read_resource", "get_prompt", "list_tools", "list_resources", "list_prompts"}}
}}

allow {{
    input.environment != "production"
}}

allow {{
    input.approval_granted == true
}}
""".strip()


# --------------------------------------------------------------------
# Cedar policy
# --------------------------------------------------------------------

DEFAULT_CEDAR_POLICY = """
// 3. Backups: hard forbid, no approval escape hatch.
forbid (
    principal,
    action,
    resource
) when { context.resource_type == "backup" };

forbid (
    principal,
    action == Action::"delete_backup",
    resource
);

// 2 + 4. Destructive actions on sensitive resources in prod need approval.
permit (
    principal,
    action in [
        Action::"delete", Action::"destroy", Action::"drop",
        Action::"truncate", Action::"purge", Action::"update",
        Action::"patch", Action::"upsert", Action::"deploy",
        Action::"rollback", Action::"rotate", Action::"revoke"
    ],
    resource
)
when {
    context.environment == "production" &&
    context.resource_type in [
        "database", "cluster", "iam_role", "cloud_resource",
        "deployment", "dns_record", "firewall_rule", "credential", "secret"
    ]
}
unless { context.approval_granted }
// @require_approval
;

// 4 (cont'd). Sensitive resource changes always need approval.
permit (
    principal,
    action in [
        Action::"delete", Action::"destroy", Action::"drop",
        Action::"create", Action::"update", Action::"patch"
    ],
    resource
)
when {
    context.resource_type in [
        "database", "cluster", "iam_role", "cloud_resource",
        "deployment", "dns_record", "firewall_rule", "credential", "secret"
    ]
}
unless { context.approval_granted }
// @require_approval
;

// 5. Prod agents: reads are allowed, writes need approval.
permit (
    principal,
    action in [
        Action::"call_tool", Action::"read_resource",
        Action::"get_prompt", Action::"list_tools",
        Action::"list_resources", Action::"list_prompts"
    ],
    resource
)
when {
    context.environment == "production" &&
    context.principal_type == "agent"
};

// Approved path: explicit ticket allows a sensitive action.
permit (
    principal,
    action,
    resource
)
when {
    context.approval_granted &&
    context.environment == "production"
}
unless { context.resource_type == "backup" };

// Non-production is permissive (bundled policy layer bounds it).
permit (
    principal,
    action,
    resource
) unless { context.environment == "production" };
""".strip()


def default_capability_bundle(
    *,
    rego_policy_id: str = "capability-bundle-rego",
    cedar_policy_id: str = "capability-bundle-cedar",
    version: str = "1.0.0",
) -> list:
    """Return the default (Rego, Cedar) provider pair.

    Wiring: the caller prepends these to the per-listing policy chain
    so that the AllowlistPolicy still bounds what the proxy *can*
    forward, but the capability bundle vetoes actions the kernel
    shouldn't even attempt. Both providers' results are independently
    audited via PolicyAuditLog; a mismatch between them is not fatal
    (the engine's AND logic fails-safely) but is visible.

    Args:
        rego_policy_id: Identifier stamped on every Rego result.
        cedar_policy_id: Identifier stamped on every Cedar result.
        version: Bundle version; reported by both providers.

    Returns:
        A list of two ``PolicyProvider`` instances ready to hand to
        ``PolicyConfig(providers=[...])`` or ``PolicyEngine``.
    """
    return [
        RegoPolicy(
            DEFAULT_REGO_MODULE,
            policy_id=rego_policy_id,
            version=version,
        ),
        CedarPolicy(
            DEFAULT_CEDAR_POLICY,
            policy_id=cedar_policy_id,
            version=version,
        ),
    ]

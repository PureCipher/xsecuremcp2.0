import { Box, Card, CardContent, Chip, Typography } from "@mui/material";
import type {
  RegistryDataFlow,
  RegistryToolListing,
} from "@/lib/registryClient";

/**
 * Iter 14.30 — Permission nutrition label.
 *
 * The previous listing detail page rendered the manifest's
 * ``data_flows`` as a bulleted list and discarded ``permissions``
 * and ``resource_access``. That made the security claims invisible
 * unless the curator opened the JSON manifest themselves.
 *
 * This component shows the same data (no backend change) as a
 * structured Apple-style nutrition label: three labeled sections
 * with plain-English descriptions and risk-aware color treatment.
 * Sensitive scopes (subprocess_exec, file_system_write, network_access
 * to public domains) get warning styling so they pop visually before
 * the curator decides to install.
 */

// ── Permission vocabulary ──────────────────────────────────────

type PermissionInfo = {
  label: string;
  description: string;
  /** Severity drives chip color. "elevated" = yellow, "high" = red. */
  severity: "low" | "elevated" | "high";
};

const PERMISSION_TABLE: Record<string, PermissionInfo> = {
  call_tool: {
    label: "Call MCP tools",
    description: "Inherent to any MCP server — exposes its tool surface to the client.",
    severity: "low",
  },
  read_resource: {
    label: "Read MCP resources",
    description: "Read resource URIs the server exposes (read-only access to its declared data set).",
    severity: "low",
  },
  write_resource: {
    label: "Write MCP resources",
    description: "Mutate resources the server exposes — create, update, or delete entries in its declared store.",
    severity: "elevated",
  },
  network_access: {
    label: "Make network calls",
    description: "Reach external HTTP/HTTPS endpoints. Combine with the data-flow section below to see what destinations are declared.",
    severity: "elevated",
  },
  file_system_read: {
    label: "Read your filesystem",
    description: "Open files on the host running the MCP server.",
    severity: "elevated",
  },
  file_system_write: {
    label: "Write your filesystem",
    description: "Create, modify, or delete files on the host running the MCP server.",
    severity: "high",
  },
  environment_read: {
    label: "Read environment variables",
    description: "Access secrets and configuration exported via env vars at the host running the MCP server.",
    severity: "elevated",
  },
  subprocess_exec: {
    label: "Spawn subprocesses",
    description: "Execute arbitrary commands on the host running the MCP server.",
    severity: "high",
  },
  sensitive_data: {
    label: "Handle sensitive data",
    description: "Self-declared: this server handles PII, PHI, financial, or otherwise sensitive material. Audit the data-flow declarations carefully.",
    severity: "high",
  },
  cross_origin: {
    label: "Cross-origin requests",
    description: "Initiate requests across security origins. Common for API integrations; review destinations.",
    severity: "elevated",
  },
};

const CLASSIFICATION_INFO: Record<
  string,
  { label: string; severity: "low" | "elevated" | "high" }
> = {
  public: { label: "Public", severity: "low" },
  internal: { label: "Internal", severity: "low" },
  confidential: { label: "Confidential", severity: "elevated" },
  restricted: { label: "Restricted", severity: "high" },
  pii: { label: "PII", severity: "high" },
  phi: { label: "PHI", severity: "high" },
  financial: { label: "Financial", severity: "high" },
};

function severitySx(severity: "low" | "elevated" | "high") {
  if (severity === "high") {
    return {
      bgcolor: "rgba(244, 63, 94, 0.10)",
      color: "#b91c1c",
      borderColor: "rgba(248, 113, 113, 0.4)",
    };
  }
  if (severity === "elevated") {
    return {
      bgcolor: "rgba(245, 158, 11, 0.12)",
      color: "#92400e",
      borderColor: "rgba(251, 191, 36, 0.4)",
    };
  }
  return {
    bgcolor: "var(--app-control-bg)",
    color: "var(--app-fg)",
    borderColor: "var(--app-border)",
  };
}

// ── Component ───────────────────────────────────────────────────

export function PermissionNutritionLabel({
  tool,
}: {
  tool: RegistryToolListing;
}) {
  const manifest = tool.manifest;
  if (!manifest) return null;

  // Permissions live as a set (string[]) in the wire shape; the
  // manifest field on RegistryToolListing is loosely typed
  // (Record<string, unknown>) so we coerce defensively.
  const rawPermissions = (manifest as { permissions?: unknown }).permissions;
  const permissions = Array.isArray(rawPermissions)
    ? (rawPermissions as string[]).filter(
        (p): p is string => typeof p === "string",
      )
    : [];

  const dataFlows: RegistryDataFlow[] = Array.isArray(
    (manifest as { data_flows?: unknown }).data_flows,
  )
    ? ((manifest as { data_flows: RegistryDataFlow[] }).data_flows ?? [])
    : [];

  const rawResourceAccess = (manifest as { resource_access?: unknown })
    .resource_access;
  const resourceAccess = Array.isArray(rawResourceAccess)
    ? (rawResourceAccess as Array<Record<string, unknown>>)
    : [];

  // Sort permissions by severity (high → elevated → low) so the
  // most-attention-grabbing scopes render first.
  const orderedPermissions = [...permissions].sort((a, b) => {
    const aSev = PERMISSION_TABLE[a]?.severity ?? "low";
    const bSev = PERMISSION_TABLE[b]?.severity ?? "low";
    const rank = { high: 0, elevated: 1, low: 2 };
    return rank[aSev] - rank[bSev];
  });

  // Compute a quick "headline severity" for the card header chip:
  // any "high" → high, else any "elevated" → elevated, else low.
  const cardSeverity: "low" | "elevated" | "high" = orderedPermissions.some(
    (p) => PERMISSION_TABLE[p]?.severity === "high",
  )
    ? "high"
    : orderedPermissions.some(
          (p) => PERMISSION_TABLE[p]?.severity === "elevated",
        )
      ? "elevated"
      : "low";

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 1,
            flexWrap: "wrap",
            mb: 1.5,
          }}
        >
          <Box>
            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Security disclosure
            </Typography>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, color: "var(--app-fg)" }}
            >
              What this tool can do
            </Typography>
            <Typography sx={{ mt: 0.25, fontSize: 12, color: "var(--app-muted)" }}>
              Declared by the publisher in the security manifest. The
              registry verifies the manifest&apos;s signature on every
              page load.
            </Typography>
          </Box>
          <Chip
            size="small"
            label={
              cardSeverity === "high"
                ? "Elevated capabilities"
                : cardSeverity === "elevated"
                  ? "Some sensitive capabilities"
                  : "Low-impact capabilities"
            }
            sx={{
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid",
              ...severitySx(cardSeverity),
            }}
          />
        </Box>

        {/* Permissions section */}
        <Box sx={{ mb: 2.5 }}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
              mb: 1,
            }}
          >
            Permissions ({orderedPermissions.length})
          </Typography>
          {orderedPermissions.length === 0 ? (
            <Typography sx={{ fontSize: 12.5, color: "var(--app-muted)" }}>
              The manifest declares no permissions beyond the implicit
              MCP call surface. Verify by reading the manifest below.
            </Typography>
          ) : (
            <Box sx={{ display: "grid", gap: 1 }}>
              {orderedPermissions.map((perm) => {
                const info =
                  PERMISSION_TABLE[perm] ?? {
                    label: perm,
                    description: "Custom permission scope. See the manifest for details.",
                    severity: "elevated" as const,
                  };
                const sx = severitySx(info.severity);
                return (
                  <Box
                    key={perm}
                    sx={{
                      display: "grid",
                      gridTemplateColumns: { xs: "1fr", sm: "auto 1fr" },
                      gap: { xs: 0.5, sm: 1.25 },
                      alignItems: "flex-start",
                      p: 1.25,
                      borderRadius: 2,
                      border: "1px solid",
                      bgcolor: sx.bgcolor,
                      borderColor: sx.borderColor,
                    }}
                  >
                    <Chip
                      size="small"
                      label={perm}
                      sx={{
                        fontFamily:
                          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        fontSize: 10.5,
                        fontWeight: 700,
                        height: 22,
                        border: "1px solid",
                        bgcolor: "var(--app-surface)",
                        color: sx.color,
                        borderColor: sx.borderColor,
                        alignSelf: "center",
                      }}
                    />
                    <Box>
                      <Typography
                        sx={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: sx.color,
                          lineHeight: 1.35,
                        }}
                      >
                        {info.label}
                      </Typography>
                      <Typography
                        sx={{
                          mt: 0.25,
                          fontSize: 12,
                          color: "var(--app-muted)",
                          lineHeight: 1.5,
                        }}
                      >
                        {info.description}
                      </Typography>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Data flows section */}
        <Box sx={{ mb: dataFlows.length > 0 || resourceAccess.length > 0 ? 2.5 : 0 }}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
              mb: 1,
            }}
          >
            Where data flows ({dataFlows.length})
          </Typography>
          {dataFlows.length === 0 ? (
            <Typography sx={{ fontSize: 12.5, color: "var(--app-muted)" }}>
              No explicit data flows were declared. For tools that
              make external calls or handle sensitive material, the
              registry recommends declaring at least one data flow.
            </Typography>
          ) : (
            <Box sx={{ display: "grid", gap: 0.75 }}>
              {dataFlows.map((flow, idx) => {
                const cls = (flow.classification ?? "internal").toLowerCase();
                const info =
                  CLASSIFICATION_INFO[cls] ?? {
                    label: flow.classification ?? "internal",
                    severity: "low" as const,
                  };
                const sx = severitySx(info.severity);
                return (
                  <Box
                    key={`${idx}-${flow.source ?? ""}-${flow.destination ?? ""}`}
                    sx={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 1,
                      flexWrap: "wrap",
                      px: 1.25,
                      py: 0.875,
                      borderRadius: 2,
                      border: "1px solid var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                    }}
                  >
                    <Chip
                      size="small"
                      label={info.label}
                      sx={{
                        fontWeight: 700,
                        fontSize: 10.5,
                        height: 22,
                        border: "1px solid",
                        ...sx,
                      }}
                    />
                    <Typography
                      sx={{
                        fontSize: 13,
                        color: "var(--app-fg)",
                        fontFamily:
                          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      }}
                    >
                      {flow.source ?? "—"}{" "}
                      <Box component="span" sx={{ color: "var(--app-muted)" }}>
                        →
                      </Box>{" "}
                      {flow.destination ?? "—"}
                    </Typography>
                    {flow.description ? (
                      <Typography
                        sx={{
                          fontSize: 12,
                          color: "var(--app-muted)",
                          flex: 1,
                          minWidth: 0,
                        }}
                      >
                        {flow.description}
                      </Typography>
                    ) : null}
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Resource access section — only render when present, since
            resource_access is optional and many manifests omit it. */}
        {resourceAccess.length > 0 ? (
          <Box>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
                mb: 1,
              }}
            >
              Resources accessed ({resourceAccess.length})
            </Typography>
            <Box sx={{ display: "grid", gap: 0.5 }}>
              {resourceAccess.map((access, idx) => {
                const uri = String(access.uri ?? access.resource_uri ?? "—");
                const mode = String(access.access_mode ?? access.mode ?? "read");
                return (
                  <Box
                    key={`${idx}-${uri}`}
                    sx={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 1,
                      flexWrap: "wrap",
                      px: 1.25,
                      py: 0.625,
                      borderRadius: 2,
                      border: "1px solid var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                    }}
                  >
                    <Chip
                      size="small"
                      label={mode}
                      sx={{
                        fontWeight: 700,
                        fontSize: 10.5,
                        height: 22,
                        bgcolor: "var(--app-surface)",
                        border: "1px solid var(--app-border)",
                        color: "var(--app-fg)",
                      }}
                    />
                    <Typography
                      sx={{
                        fontSize: 12.5,
                        color: "var(--app-fg)",
                        fontFamily:
                          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        wordBreak: "break-all",
                      }}
                    >
                      {uri}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </Box>
        ) : null}
      </CardContent>
    </Card>
  );
}

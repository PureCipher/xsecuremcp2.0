import { redirect } from "next/navigation";

import { Box, Typography } from "@mui/material";

import {
  getAccountabilityLog,
  getSecurityHealth,
  requireAdminRole,
} from "@/lib/registryClient";
import { ReflexiveManager } from "./ReflexiveManager";

export default async function ReflexivePage() {
  const { allowed } = await requireAdminRole();

  if (!allowed) {
    redirect("/registry/app");
  }

  const accountabilityData = await getAccountabilityLog();
  const healthData = await getSecurityHealth();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Reflexive Execution
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Monitor, introspect, and gate agent behavior
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Examine behavioral drift, threat levels, compliance status, and execution verdicts for every actor in the system. Pre-execution gating halts, throttles, or requires confirmation for high-risk operations.
        </Typography>
      </Box>

      <ReflexiveManager
          initialAccountability={
            accountabilityData?.entries?.map(entry => ({
              ...entry,
              threat_level: entry.threat_level ?? "unknown",
              compliance_status: entry.compliance_status ?? "unknown",
              verdict: entry.verdict ?? "unknown",
              timestamp: entry.timestamp ?? new Date().toISOString(),
            })) ?? []
          }
          initialHealth={
            healthData
              ? {
                  overall_status: (healthData.status as "ok" | "not_configured" | "degraded") ?? "not_configured",
                  component_count: healthData.component_count ?? 0,
                  components: healthData.components
                    ? Object.entries(healthData.components).map(([name, status]) => ({
                        name,
                        status: (status as "ok" | "not_configured") ?? "not_configured",
                      }))
                    : undefined,
                  timestamp: healthData.timestamp,
                }
              : undefined
          }
        />
    </Box>
  );
}

import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import {
  getAccountabilityLog,
  requireAdminRole,
} from "@/lib/registryClient";
import { ReflexiveManager } from "./ReflexiveManager";

export default async function ReflexivePage() {
  const { allowed } = await requireAdminRole();

  if (!allowed) {
    redirect("/registry/app");
  }

  const accountabilityData = await getAccountabilityLog();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Reflexive Execution"
        title="Monitor, introspect, and gate agent behavior"
        description="Examine behavioral drift, threat levels, compliance status, and execution verdicts for every actor in the system. Pre-execution gating halts, throttles, or requires confirmation for high-risk operations."
      />

      <ReflexiveManager
        initialAccountability={
          accountabilityData?.entries?.map((entry) => ({
            ...entry,
            threat_level: entry.threat_level ?? "unknown",
            compliance_status: entry.compliance_status ?? "unknown",
            verdict: entry.verdict ?? "unknown",
            timestamp: entry.timestamp ?? new Date().toISOString(),
          })) ?? []
        }
      />
    </Box>
  );
}

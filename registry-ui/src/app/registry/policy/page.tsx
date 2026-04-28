import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import {
  getPolicyManagement,
  getRegistrySession,
  requirePolicyRole,
} from "@/lib/registryClient";
import { PolicyManager } from "./PolicyManager";

export default async function PolicyPage() {
  const { allowed } = await requirePolicyRole();
  const sessionPayload = await getRegistrySession();
  const username = sessionPayload?.session?.username ?? null;
  // Iter 14.18 — pull the role so PolicyManager can pick a sensible
  // default landing tab (admin → metrics, reviewer → proposals,
  // curator/viewer → catalog) when the user hasn't pinned one.
  const role = sessionPayload?.session?.role ?? null;

  if (!allowed) {
    redirect("/registry/app");
  }

  const policyData = await getPolicyManagement();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Policy management"
        title="Propose, review, and apply SecureMCP rules"
        description="Draft changes first, run a quick simulation, approve them before they go live, and keep every draft tied to the live policy version it came from."
      />

      <PolicyManager
        initialData={policyData ?? {}}
        currentUsername={username}
        currentRole={role}
      />
    </Box>
  );
}

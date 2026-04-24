import { redirect } from "next/navigation";

import { Box, Typography } from "@mui/material";

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

  if (!allowed) {
    redirect("/registry/app");
  }

  const policyData = await getPolicyManagement();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Policy management
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Propose, review, and apply SecureMCP rules
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Draft changes first, run a quick simulation, approve them before they go live, and keep every draft tied to
          the live policy version it came from.
        </Typography>
      </Box>

      <PolicyManager initialData={policyData ?? {}} currentUsername={username} />
    </Box>
  );
}

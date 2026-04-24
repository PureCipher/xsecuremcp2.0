import { redirect } from "next/navigation";

import { Box, Typography } from "@mui/material";

import { listInstitutions, listJurisdictions, requireAdminRole } from "@/lib/registryClient";
import { ConsentManager } from "./ConsentManager";

export default async function ConsentPage() {
  const { allowed } = await requireAdminRole();

  if (!allowed) {
    redirect("/registry/app");
  }

  const jurisdictionsData = await listJurisdictions();
  const institutionsData = await listInstitutions();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Federated Consent
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Evaluate, manage, and visualize consent graphs
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Test consent queries across jurisdictions, view access rights matrices, manage jurisdiction policies, and explore consent relationships between agents and resources.
        </Typography>
      </Box>

      <ConsentManager initialJurisdictions={jurisdictionsData} initialInstitutions={institutionsData} />
    </Box>
  );
}

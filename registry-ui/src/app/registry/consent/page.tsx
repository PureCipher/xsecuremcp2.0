import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

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
      <RegistryPageHeader
        eyebrow="Federated Consent"
        title="Evaluate, manage, and visualize consent graphs"
        description="Test consent queries across jurisdictions, view access rights matrices, manage jurisdiction policies, and explore consent relationships between agents and resources."
      />

      <ConsentManager initialJurisdictions={jurisdictionsData} initialInstitutions={institutionsData} />
    </Box>
  );
}

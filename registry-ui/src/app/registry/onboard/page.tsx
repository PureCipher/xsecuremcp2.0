import { redirect } from "next/navigation";
import { Box } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
import { requirePublisherRole } from "@/lib/registryClient";

import { OnboardWizard } from "./wizard/OnboardWizard";

export default async function OnboardPage() {
  // Curator workflow shares the publisher RBAC role (hybrid model:
  // anyone with publisher rights can submit; reviewer approves before
  // it goes live).
  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Curator onboarding"
        title="Onboard a third-party MCP server"
        description="Vouch for an existing public MCP server. The registry pins its URL, observes its capability surface, and signs a curator-attested listing. The author of the upstream is unaware of and unaffected by the listing."
      />
      <OnboardWizard />
    </Box>
  );
}

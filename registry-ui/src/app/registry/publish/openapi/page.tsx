import { redirect } from "next/navigation";
import { Box } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
import { requirePublisherRole } from "@/lib/registryClient";
import { OpenApiPublishWizard } from "./wizard/OpenApiPublishWizard";

export default async function OpenApiPublishPage() {
  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Publisher onboarding"
        title="Create hosted SecureMCP toolset (OpenAPI)"
        description="Multi-step wizard: fetch an OpenAPI document, select operations, generate a toolset, run preflight, and publish."
      />

      <OpenApiPublishWizard />
    </Box>
  );
}


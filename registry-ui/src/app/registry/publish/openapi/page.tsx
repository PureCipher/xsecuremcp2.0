import { redirect } from "next/navigation";
import { Box, Typography } from "@mui/material";

import { requirePublisherRole } from "@/lib/registryClient";
import { OpenApiPublishWizard } from "./wizard/OpenApiPublishWizard";

export default async function OpenApiPublishPage() {
  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Publisher onboarding
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Create hosted SecureMCP toolset (OpenAPI)
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, maxWidth: 820, color: "var(--app-muted)" }}>
          Multi-step wizard: fetch an OpenAPI document, select operations, generate a toolset, run preflight, and
          publish.
        </Typography>
      </Box>

      <OpenApiPublishWizard />
    </Box>
  );
}


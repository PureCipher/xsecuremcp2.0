import { listPublishers, type PublisherSummary } from "@/lib/registryClient";
import { PublishersDirectory } from "@/app/registry/publishers/PublishersDirectory";

import { Box, Typography } from "@mui/material";

export default async function PublicPublishersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Publisher directory
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          People and teams behind the tools
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
          Browse publishers with live listings in the registry. Open any profile to see their tools and trust signals.
        </Typography>
      </Box>

      <PublishersDirectory publishers={publishers} basePath="/public/publishers" toolsHref="/public/tools" publicView />
    </Box>
  );
}


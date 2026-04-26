import { listPublishers, type PublisherSummary } from "@/lib/registryClient";
import { ServersDirectory } from "@/app/registry/servers/ServersDirectory";

import { Box, Typography } from "@mui/material";

export default async function PublicServersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          MCP Servers
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Server directory
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Browse server profiles derived from publishers that have live tools in the registry.
        </Typography>
      </Box>

      <ServersDirectory servers={publishers} basePath="/public/servers" toolsHref="/public/tools" publicView />
    </Box>
  );
}


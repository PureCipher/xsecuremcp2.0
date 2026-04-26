import { RegistryPageHeader } from "@/components/security";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";
import { ServersDirectory } from "./ServersDirectory";

import { Box } from "@mui/material";

export default async function ServersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="MCP Servers"
        title="Onboard and introspect servers"
        description="Discover tools exposed by each MCP server, apply Governance attachments, and track access outcomes via the ledger and observability stream."
      />

      <ServersDirectory
        servers={publishers}
        onboardHref="/registry/servers/onboard"
        toolsHref="/registry/app"
      />
    </Box>
  );
}


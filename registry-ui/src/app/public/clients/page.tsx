import { ClientsDirectory } from "@/app/registry/clients/ClientsDirectory";

import { Box, Typography } from "@mui/material";

export default function PublicClientsPage() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Clients
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "text.primary" }}>
          Client directory
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Public client directory is in development. When live, this page will list MCP client identities and their compatibility profile against the registry catalog.
        </Typography>
      </Box>

      <ClientsDirectory serversHref="/public/servers" publicView />
    </Box>
  );
}


import { EmptyState } from "@/components/security";

import { Box, Card, CardContent, Typography } from "@mui/material";

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
          Public view of MCP clients (stub). This will list public client identities and compatibility metadata once backend integration is wired.
        </Typography>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <EmptyState
            title="No public clients listed yet"
            message="Client onboarding is part of the console experience. This page becomes a public directory once client metadata is published."
          />
        </CardContent>
      </Card>
    </Box>
  );
}


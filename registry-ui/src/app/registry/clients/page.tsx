import Link from "next/link";

import { EmptyState } from "@/components/security";

import { Box, Button, Card, CardContent, Typography } from "@mui/material";

export default function ClientsPage() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Clients
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Onboard and bind clients
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          UI skeleton for connecting client identities to MCP servers with effective Policy/Contract/Consent controls.
        </Typography>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box
            sx={{
              display: "flex",
              flexDirection: { xs: "column", sm: "row" },
              gap: 2,
              alignItems: { sm: "center" },
              justifyContent: "space-between",
            }}
          >
            <Box>
              <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>Client registry</Typography>
              <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                After backend integration, this will list onboarded clients and their access bindings.
              </Typography>
            </Box>
            <Link href="/registry/clients/onboard" style={{ textDecoration: "none" }}>
              <Button
                variant="contained"
                sx={{
                  borderRadius: 999,
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  "&:hover": { bgcolor: "var(--app-accent)" },
                  alignSelf: { xs: "flex-start", sm: "auto" },
                }}
              >
                Onboard client
              </Button>
            </Link>
          </Box>

          <Box sx={{ mt: 3 }}>
            <EmptyState
              title="No clients onboarded yet"
              message="Connect a client identity, select the MCP servers (and optionally tool scope), then run a simulation to validate effective access."
            />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}


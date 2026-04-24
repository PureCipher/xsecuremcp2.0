import { redirect } from "next/navigation";
import Link from "next/link";
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";

import { getMyListings, getRegistrySession, requirePublisherRole } from "@/lib/registryClient";

export default async function PublisherGetStartedPage() {
  const sessionPayload = await getRegistrySession();
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  if (authEnabled && session == null) {
    redirect("/login");
  }

  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  const mine = (await getMyListings()) ?? {};
  const count = typeof mine.count === "number" ? mine.count : Array.isArray(mine.tools) ? mine.tools.length : 0;
  if (count > 0) {
    redirect("/registry/publish/mine");
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header">
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Publisher onboarding
        </Typography>
        <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: "var(--app-fg)" }}>
          Get started publishing
        </Typography>
        <Typography sx={{ mt: 1, maxWidth: 760, fontSize: 12, color: "var(--app-muted)" }}>
          Pick the path that matches where you are today. You can always switch later.
        </Typography>
      </Box>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>I already host an MCP server</Typography>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                You run the server; the registry stores the listing, versions, and security manifest so clients can discover and verify it.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                <Chip size="small" label="MCP" sx={{ borderRadius: 999 }} />
                <Chip size="small" label="SecureMCP" sx={{ borderRadius: 999 }} />
                <Chip size="small" label="Version history" sx={{ borderRadius: 999 }} />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link href="/registry/publish?publish_mode=external&server_type=mcp" legacyBehavior passHref>
                  <Button component="a" variant="outlined" sx={{ borderRadius: 999, textTransform: "none" }}>
                    Publish MCP server
                  </Button>
                </Link>
                <Link href="/registry/publish?publish_mode=external&server_type=securemcp" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="contained"
                    sx={{
                      borderRadius: 999,
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      "&:hover": { bgcolor: "var(--app-accent)" },
                      textTransform: "none",
                    }}
                  >
                    Publish SecureMCP server
                  </Button>
                </Link>
              </Box>
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>I have a REST/OpenAPI API</Typography>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Paste an OpenAPI URL, pick endpoints, and the registry hosts a SecureMCP server endpoint for your selected toolset.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                <Chip size="small" label="OpenAPI → Tools" sx={{ borderRadius: 999 }} />
                <Chip size="small" label="Hosted endpoint" sx={{ borderRadius: 999 }} />
                <Chip size="small" label="SecureMCP" sx={{ borderRadius: 999 }} />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link href="/registry/publish?publish_mode=openapi" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="contained"
                    sx={{
                      borderRadius: 999,
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      "&:hover": { bgcolor: "var(--app-accent)" },
                      textTransform: "none",
                    }}
                  >
                    Create hosted SecureMCP toolset
                  </Button>
                </Link>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Box>
        <Link href="/registry/publish/mine" className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]">
          Skip → My listings
        </Link>
      </Box>
    </Box>
  );
}


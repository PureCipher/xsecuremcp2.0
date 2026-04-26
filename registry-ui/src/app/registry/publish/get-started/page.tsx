import { redirect } from "next/navigation";
import Link from "next/link";
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
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
      <RegistryPageHeader
        eyebrow="Publisher onboarding"
        title="Get started publishing"
        description="Pick the path that matches where you are today. You can always switch later."
      />

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <Card variant="outlined">
          <CardContent>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>I built an MCP server</Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                You authored the code; the registry stores your listing, version history, and signed security manifest so clients can discover and verify it.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                <Chip size="small" label="MCP" />
                <Chip size="small" label="SecureMCP" />
                <Chip size="small" label="Version history" />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link
                  href="/registry/publish?from=onboarding&publish_mode=external&server_type=mcp"
                  style={{ display: "inline-flex", textDecoration: "none" }}
                >
                  <Button component="span" variant="outlined">
                    Publish MCP server
                  </Button>
                </Link>
                <Link
                  href="/registry/publish?from=onboarding&publish_mode=external&server_type=securemcp"
                  style={{ display: "inline-flex", textDecoration: "none" }}
                >
                  <Button
                    component="span"
                    variant="contained"
                    sx={{
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

        <Card variant="outlined">
          <CardContent>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
                I want to onboard a server I trust
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Curator vouches for an existing public MCP server. The
                registry pins its URL, observes its capability surface,
                and signs a third-party attestation distinct from
                author-attested listings. No coding required.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                <Chip size="small" label="Curator" />
                <Chip size="small" label="Third-party" />
                <Chip size="small" label="No coding" />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link
                  href="/registry/onboard"
                  style={{ display: "inline-flex", textDecoration: "none" }}
                >
                  <Button
                    component="span"
                    variant="contained"
                    sx={{
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      "&:hover": { bgcolor: "var(--app-accent)" },
                      textTransform: "none",
                    }}
                  >
                    Onboard a third-party server
                  </Button>
                </Link>
              </Box>
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ gridColumn: { lg: "1 / -1" } }}>
          <CardContent>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>I have a REST/OpenAPI API</Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Paste an OpenAPI URL, pick endpoints, and the registry hosts a SecureMCP server endpoint for your selected toolset.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                <Chip size="small" label="OpenAPI -> Tools" />
                <Chip size="small" label="Hosted endpoint" />
                <Chip size="small" label="SecureMCP" />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link
                  href="/registry/publish/openapi"
                  style={{ display: "inline-flex", textDecoration: "none" }}
                >
                  <Button
                    component="span"
                    variant="contained"
                    sx={{
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
        <Box
          component="a"
          href="/registry/publish/mine"
          sx={{
            display: "inline-flex",
            color: "var(--app-muted)",
            textDecoration: "none",
            "&:hover": { color: "var(--app-fg)", textDecoration: "underline" },
          }}
        >
          <Typography variant="caption" sx={{ fontWeight: 600 }}>
            Skip → My listings
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}


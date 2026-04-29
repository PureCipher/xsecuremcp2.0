import { redirect } from "next/navigation";
import Link from "next/link";
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
import { getRegistrySession, requirePublisherRole } from "@/lib/registryClient";

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
                Paste a manifest and publish directly, or point the registry at your running server and let it introspect the capabilities automatically.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
                <Chip size="small" label="MCP" />
                <Chip size="small" label="SecureMCP" />
              </Box>
              <Box sx={{ display: "grid", gap: 1, mt: 2 }}>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  <Link href="/registry/publish?from=onboarding&publish_mode=external&server_type=mcp" style={{ display: "inline-flex", textDecoration: "none" }}>
                    <Button component="span" variant="outlined" sx={{ textTransform: "none" }}>Paste manifest (MCP)</Button>
                  </Link>
                  <Link href="/registry/publish?from=onboarding&publish_mode=external&server_type=securemcp" style={{ display: "inline-flex", textDecoration: "none" }}>
                    <Button component="span" variant="outlined" sx={{ textTransform: "none" }}>Paste manifest (SecureMCP)</Button>
                  </Link>
                </Box>
                <Typography sx={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--app-muted)" }}>
                  Or connect a running server
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                  {[
                    { label: "HTTP / SSE endpoint", href: "/registry/onboard?mode=author" },
                    { label: "PyPI package", href: "/registry/onboard?mode=author" },
                    { label: "npm package", href: "/registry/onboard?mode=author" },
                    { label: "Docker image", href: "/registry/onboard?mode=author" },
                  ].map(({ label, href }) => (
                    <Link key={label} href={href} style={{ display: "inline-flex", textDecoration: "none" }}>
                      <Button component="span" size="small" variant="contained" sx={{ bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" }, textTransform: "none" }}>
                        {label}
                      </Button>
                    </Link>
                  ))}
                </Box>
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
                Vouch for an existing MCP server you trust. The registry introspects it, pins the upstream, and signs a curator-attested listing. The original author is unaware.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
                <Chip size="small" label="Curator" />
                <Chip size="small" label="Third-party" />
                <Chip size="small" label="No coding" />
              </Box>
              <Box sx={{ display: "grid", gap: 1, mt: 2 }}>
                <Typography sx={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--app-muted)" }}>
                  Supported channels
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                  {[
                    { label: "HTTP / SSE endpoint", href: "/registry/onboard" },
                    { label: "PyPI package", href: "/registry/onboard" },
                    { label: "npm package", href: "/registry/onboard" },
                    { label: "Docker image", href: "/registry/onboard" },
                  ].map(({ label, href }) => (
                    <Link key={label} href={href} style={{ display: "inline-flex", textDecoration: "none" }}>
                      <Button component="span" size="small" variant="contained" sx={{ bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" }, textTransform: "none" }}>
                        {label}
                      </Button>
                    </Link>
                  ))}
                </Box>
              </Box>
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ gridColumn: { lg: "1 / -1" } }}>
          <CardContent>
            <Stack spacing={1}>
              <Typography sx={{ fontWeight: 800, color: "var(--app-fg)" }}>I have a REST / OpenAPI API</Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Paste an OpenAPI spec URL, pick the endpoints you want, and the registry hosts a SecureMCP gateway that converts them into MCP tools automatically.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
                <Chip size="small" label="OpenAPI → Tools" />
                <Chip size="small" label="Hosted gateway" />
                <Chip size="small" label="SecureMCP" />
              </Box>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2 }}>
                <Link href="/registry/publish/openapi" style={{ display: "inline-flex", textDecoration: "none" }}>
                  <Button component="span" variant="contained" sx={{ bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" }, textTransform: "none" }}>
                    Create hosted toolset from OpenAPI
                  </Button>
                </Link>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Link href="/registry/publish/mine" style={{ textDecoration: "none" }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-muted)", "&:hover": { color: "var(--app-fg)" } }}>
          ← My listings
        </Typography>
      </Link>
    </Box>
  );
}


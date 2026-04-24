"use server";

import Link from "next/link";

import { Alert, Box, Button, Card, CardContent, Chip, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";

import {
  getPublisherProfile,
  listPublishers,
  type PublisherSummary,
  type RegistryToolListing,
  verifyTool,
  getToolDetail,
} from "@/lib/registryClient";
import { JsonViewer, KeyValuePanel, EmptyState } from "@/components/security";

function getStringParam(param: string | string[] | undefined): string | undefined {
  if (typeof param !== "string") return undefined;
  return param.trim() ? param : undefined;
}

export default async function AccessStudioPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  const clientId = getStringParam(searchParams?.clientId);
  const serverIdParam = getStringParam(searchParams?.serverId);
  const toolName = getStringParam(searchParams?.toolName);

  const serverId = serverIdParam ? decodeURIComponent(serverIdParam) : undefined;

  const profile = serverId ? await getPublisherProfile(serverId) : null;
  const listings: RegistryToolListing[] = profile?.listings ?? [];

  let error: string | null = null;
  let toolDetail: RegistryToolListing | null = null;
  let verification:
    | Awaited<ReturnType<typeof verifyTool>>
    | null = null;

  if (serverId && toolName) {
    try {
      const detail = await getToolDetail(toolName);
      if (detail && "tool_name" in detail) {
        toolDetail = detail as RegistryToolListing;
      }

      verification = await verifyTool(toolName);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load tool verification";
    }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Access Studio
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Simulate MCP tool eligibility
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, maxWidth: 900, color: "var(--app-muted)" }}>
          MCP-only phase: server tool inventory + registry certification/verification preview. Contract/ledger/consent enforcement comes next.
        </Typography>
      </Box>

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Link href="/registry/clients" legacyBehavior passHref>
          <Button component="a" variant="text" sx={{ color: "var(--app-muted)" }}>
            ← Clients
          </Button>
        </Link>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            MCP simulation query
          </Typography>
          <Box component="form" method="GET" sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <TextField
              name="clientId"
              defaultValue={clientId ?? ""}
              label="Client ID"
              placeholder="e.g., client-123"
              size="small"
              fullWidth
            />

            <FormControl size="small" fullWidth>
              <InputLabel id="serverIdLabel">MCP Server</InputLabel>
              <Select labelId="serverIdLabel" label="MCP Server" name="serverId" defaultValue={serverIdParam ?? ""}>
                <MenuItem value="">
                  <em>Select a server (publisher)</em>
                </MenuItem>
                {publishers.map((p) => (
                  <MenuItem key={p.publisher_id} value={p.publisher_id}>
                    {p.display_name ?? p.publisher_id}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" fullWidth sx={{ gridColumn: { md: "1 / -1" } }}>
              <InputLabel id="toolNameLabel">Tool (optional)</InputLabel>
              <Select
                labelId="toolNameLabel"
                label="Tool (optional)"
                name="toolName"
                defaultValue={toolName ?? ""}
                disabled={!serverId || listings.length === 0}
              >
                <MenuItem value="">
                  <em>Use server-level resource</em>
                </MenuItem>
                {listings.map((l) => (
                  <MenuItem key={l.tool_name} value={l.tool_name}>
                    {l.display_name ?? l.tool_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box sx={{ gridColumn: { md: "1 / -1" }, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
              <Button
                type="submit"
                variant="contained"
                sx={{ borderRadius: 999, bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" } }}
              >
                Run simulation
              </Button>

              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Server:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {serverId ? serverId : "—"}
                </Box>
                {toolName ? (
                  <>
                    {" "}
                    · Tool:{" "}
                    <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                      {toolName}
                    </Box>
                  </>
                ) : null}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {error ? <Alert severity="error">Simulation failed: {error}</Alert> : null}

      {serverId ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Server tool inventory
            </Typography>

          {profile?.error ? (
            <EmptyState
              title="Server profile unavailable"
              message="The registry backend returned an error for this server profile."
            />
          ) : (
            <Box sx={{ mt: 2, display: "grid", gap: 2 }}>
              <KeyValuePanel
                title="Server snapshot (MCP-only)"
                entries={[
                  { label: "server_id", value: serverId },
                  {
                    label: "tool_count",
                    value: String(profile?.summary?.tool_count ?? listings.length),
                  },
                  {
                    label: "client_id (optional)",
                    value: clientId ?? "—",
                  },
                ]}
              />

              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                {listings.length === 0 ? (
                  <EmptyState
                    title="No tool listings"
                    message="This server profile currently has no tool listings in the registry."
                  />
                ) : (
                  listings.slice(0, 8).map((tool) => (
                    <Card
                      key={tool.tool_name}
                      variant="outlined"
                      sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
                    >
                      <CardContent sx={{ p: 2 }}>
                        <Box sx={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 1.5 }}>
                          <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                            {tool.display_name ?? tool.tool_name}
                          </Typography>
                          <Chip
                            size="small"
                            label={tool.certification_level ?? "unlisted"}
                            sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11 }}
                          />
                        </Box>
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          {tool.description ?? "No description provided."}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))
                )}
              </Box>

              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                  Showing up to 8 tools for performance. Use the Tool dropdown to inspect certification details.
              </Typography>
            </Box>
          )}
          </CardContent>
        </Card>
      ) : (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
          <EmptyState
            title="Pick a server to simulate"
            message="Choose a server (publisher) and optionally a tool, then click “Run simulation”."
          />
          </CardContent>
        </Card>
      )}

      {toolName ? (
        <Card
          component="section"
          variant="outlined"
          sx={{
            borderRadius: 4,
            borderColor: "var(--app-border)",
            bgcolor: "var(--app-surface)",
            boxShadow: "none",
          }}
        >
          <CardContent sx={{ p: 3 }}>
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Tool verification (registry)
          </Typography>
          <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 0.95fr" } }}>
            <KeyValuePanel
              title="MCP tool eligibility preview"
              entries={[
                { label: "tool_name", value: toolName },
                {
                  label: "listed_in_selected_server",
                  value: listings.some((l) => l.tool_name === toolName) ? "true" : "false",
                },
                {
                  label: "certification_level",
                  value:
                    (toolDetail?.certification_level ?? listings.find((l) => l.tool_name === toolName)?.certification_level) ??
                    "—",
                },
              ]}
            />

            <Box sx={{ display: "grid", gap: 2 }}>
              <KeyValuePanel
                title="Verification details"
                entries={[
                  {
                    label: "signature_valid",
                    value: verification?.verification?.signature_valid ? "true" : "false",
                  },
                  {
                    label: "manifest_match",
                    value: verification?.verification?.manifest_match ? "true" : "false",
                  },
                  {
                    label: "issues",
                    value: verification?.verification?.issues?.length
                      ? verification.verification.issues.join("; ")
                      : "—",
                  },
                ]}
              />
              {verification ? (
                <JsonViewer data={verification} title="Raw tool verification response" defaultExpanded={false} />
              ) : (
                <EmptyState title="No verification loaded" message="Run simulation again to fetch verification." />
              )}
            </Box>
          </Box>
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );
}


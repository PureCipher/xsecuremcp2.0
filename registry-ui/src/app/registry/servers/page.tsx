import Link from "next/link";

import { EmptyState } from "@/components/security";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

import { Box, Button, Card, CardActionArea, CardContent, Chip, Typography } from "@mui/material";

export default async function ServersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          MCP Servers
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Onboard and introspect servers
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Discover tools exposed by each MCP server, apply Governance attachments, and track access outcomes via the ledger and observability stream.
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
              <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>Server inventory</Typography>
              <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                Live directory backed by the registry backend.
              </Typography>
            </Box>
            <Link href="/registry/servers/onboard" legacyBehavior passHref>
              <Button
                component="a"
                variant="contained"
                sx={{
                  borderRadius: 999,
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  "&:hover": { bgcolor: "var(--app-accent)" },
                  alignSelf: { xs: "flex-start", sm: "auto" },
                }}
              >
                Onboard MCP server
              </Button>
            </Link>
          </Box>

          <Box sx={{ mt: 3 }}>
            {publishers.length === 0 ? (
              <EmptyState
                title="No servers visible yet"
                message="Once a publisher is present in the registry, it will appear here as an MCP server source."
              />
            ) : (
              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                {publishers.map((publisher) => (
                  <Card
                    key={publisher.publisher_id}
                    variant="outlined"
                    sx={{
                      borderRadius: 3,
                      borderColor: "var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                      boxShadow: "none",
                    }}
                  >
                    <Link href={`/registry/servers/${encodeURIComponent(publisher.publisher_id)}`} legacyBehavior passHref>
                      <CardActionArea
                        component="a"
                        sx={{ borderRadius: 3, p: 0, "&:hover": { backgroundColor: "transparent" } }}
                      >
                        <CardContent sx={{ p: 2 }}>
                      <Box sx={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 1 }}>
                        <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                          {publisher.display_name ?? publisher.publisher_id}
                        </Typography>
                        {publisher.trust_score?.overall != null ? (
                          <Chip
                            size="small"
                            label={`Trust ${publisher.trust_score.overall.toFixed(1)}`}
                            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11 }}
                          />
                        ) : null}
                      </Box>

                      <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                        {publisher.summary ?? "No summary provided."}
                      </Typography>

                      <Typography sx={{ mt: 1.5, fontSize: 11, color: "var(--app-muted)" }}>
                        {publisher.tool_count ?? 0} tool{(publisher.tool_count ?? 0) === 1 ? "" : "s"} in this registry
                      </Typography>
                        </CardContent>
                      </CardActionArea>
                    </Link>
                  </Card>
                ))}
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}


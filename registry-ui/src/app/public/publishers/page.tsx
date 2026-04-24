import Link from "next/link";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

import { Box, Card, CardContent, Chip, Typography } from "@mui/material";

export default async function PublicPublishersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Publisher directory
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          People and teams behind the tools
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
          Browse publishers with live listings in the registry. Open any profile to see their tools and trust signals.
        </Typography>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          {publishers.length === 0 ? (
            <Typography sx={{ color: "var(--app-muted)" }}>
              No publishers are visible yet. Once tools are in the registry, their publishers will appear here.
            </Typography>
          ) : (
            <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              {publishers.map((publisher) => (
                <Link
                  key={publisher.publisher_id}
                  href={`/public/publishers/${encodeURIComponent(publisher.publisher_id)}`}
                  legacyBehavior
                  passHref
                >
                  <Card
                    component="a"
                    variant="outlined"
                    sx={{
                      textDecoration: "none",
                      borderRadius: 3,
                      borderColor: "var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                      boxShadow: "none",
                      "&:hover": { borderColor: "var(--app-accent)" },
                    }}
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
                  </Card>
                </Link>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}


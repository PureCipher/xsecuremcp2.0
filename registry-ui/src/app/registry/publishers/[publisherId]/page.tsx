import Link from "next/link";
import { Box, Card, CardActionArea, CardContent, Chip, Typography } from "@mui/material";
import {
  getPublisherProfile,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { CertificationBadge } from "@/components/security";

export default async function PublisherProfilePage(props: { params: Promise<{ publisherId: string }> }) {
  const { publisherId } = await props.params;
  const decodedId = decodeURIComponent(publisherId);
  const profile = await getPublisherProfile(decodedId);

  if (!profile) {
    return (
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Publisher not found
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            No publisher profile is available for{" "}
            <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
              {decodedId}
            </Box>
            .
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/publishers" legacyBehavior passHref>
              <Box
                component="a"
                sx={{
                  display: "inline-flex",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--app-muted)",
                  textDecoration: "none",
                  "&:hover": { color: "var(--app-fg)" },
                }}
              >
                ← Back to all publishers
              </Box>
            </Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (profile.error) {
    return (
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Unable to load publisher
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>{profile.error}</Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/publishers" legacyBehavior passHref>
              <Box
                component="a"
                sx={{
                  display: "inline-flex",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--app-muted)",
                  textDecoration: "none",
                  "&:hover": { color: "var(--app-fg)" },
                }}
              >
                ← Back to all publishers
              </Box>
            </Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const summary: PublisherSummary = profile.summary ?? { publisher_id: decodedId };
  const listings: RegistryToolListing[] = profile.listings ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, alignItems: { sm: "flex-end" }, justifyContent: "space-between" }}>
        <Box>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Publisher profile
          </Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: "var(--app-fg)" }}>
            {summary.display_name ?? summary.publisher_id}
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            {summary.publisher_id} · {summary.tool_count ?? 0} tool{(summary.tool_count ?? 0) === 1 ? "" : "s"} in this registry
          </Typography>
        </Box>
        {summary.trust_score?.overall != null ? (
          <Chip
            size="small"
            label={`Trust score ${summary.trust_score.overall.toFixed(1)}`}
            sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, alignSelf: { xs: "flex-start", sm: "auto" } }}
          />
        ) : null}
      </Box>

      <Box component="section" sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.2fr) minmax(0,1fr)" } }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              About
            </Typography>
            <Typography sx={{ mt: 1.5, fontSize: 13, color: "var(--app-muted)" }}>
              {summary.description ?? "This publisher has not added a profile description yet."}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Snapshot
            </Typography>
            <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
              <li>
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Tools:</Box> {summary.tool_count ?? listings.length}
              </li>
              {summary.verified_tool_count != null ? (
                <li>
                  <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Verified tools:</Box> {summary.verified_tool_count}
                </li>
              ) : null}
            </Box>
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Tools from this publisher
          </Typography>
          {listings.length === 0 ? (
            <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
              This publisher does not have any live verified tools yet.
            </Typography>
          ) : (
            <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              {listings.map((tool) => (
                <Card
                  key={tool.tool_name}
                  variant="outlined"
                  sx={{
                    borderRadius: 3,
                    borderColor: "var(--app-border)",
                    bgcolor: "var(--app-control-bg)",
                    boxShadow: "none",
                  }}
                >
                  <Link href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`} legacyBehavior passHref>
                    <CardActionArea component="a" sx={{ borderRadius: 3 }}>
                      <CardContent sx={{ p: 2 }}>
                        <Box sx={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 1 }}>
                          <Box>
                            <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                              {tool.display_name ?? tool.tool_name}
                            </Typography>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>{tool.tool_name}</Typography>
                          </Box>
                          <CertificationBadge level={tool.certification_level} />
                        </Box>
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          {tool.description ?? "No description provided."}
                        </Typography>
                      </CardContent>
                    </CardActionArea>
                  </Link>
                </Card>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      <Box sx={{ pt: 1 }}>
        <Link href="/registry/publishers" legacyBehavior passHref>
          <Box
            component="a"
            sx={{
              display: "inline-flex",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--app-muted)",
              textDecoration: "none",
              "&:hover": { color: "var(--app-fg)" },
            }}
          >
            ← Back to all publishers
          </Box>
        </Link>
      </Box>
    </Box>
  );
}

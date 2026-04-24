import Link from "next/link";

import {
  getPublisherProfile,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { ServerDetailTabs } from "./ServerDetailTabs";

import { Box, Card, CardContent, Chip, Typography } from "@mui/material";

export default async function ServerDetailPage(props: {
  params: Promise<{ serverId: string }>;
}) {
  const { serverId } = await props.params;
  const decodedId = decodeURIComponent(serverId);

  const profile = await getPublisherProfile(decodedId);
  if (!profile || profile.error) {
    return (
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Unable to load server
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            No server profile is available for{" "}
            <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
              {decodedId}
            </Box>
            .
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/servers" className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]">
              ← Back to MCP servers
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
            MCP server profile
          </Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: "var(--app-fg)" }}>
            {summary.display_name ?? summary.publisher_id}
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            {summary.publisher_id} · {summary.tool_count ?? listings.length} tool{(summary.tool_count ?? listings.length) === 1 ? "" : "s"} in this registry
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

      <ServerDetailTabs serverId={decodedId} summary={summary} listings={listings} />

      <Box sx={{ pt: 1 }}>
        <Link href="/registry/servers" className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]">
          ← Back to MCP servers
        </Link>
      </Box>
    </Box>
  );
}


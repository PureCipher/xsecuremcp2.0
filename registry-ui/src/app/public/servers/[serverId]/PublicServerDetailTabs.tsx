"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Box, Card, CardContent, Tab, Tabs, Typography } from "@mui/material";

import { CertificationBadge, EmptyState, KeyValuePanel } from "@/components/security";
import type { PublisherSummary, RegistryToolListing } from "@/lib/registryClient";

// The public surface shows only the two tabs that are backed by real
// data (Overview + Tools). Governance and Observability tabs were
// previously rendered with `(stub)` strings and developer scaffolding
// notes visible to anonymous visitors — we now hide them entirely
// until the backend server-binding layer is wired.
type TabKey = "overview" | "tools";

export function PublicServerDetailTabs({
  serverId,
  summary,
  listings,
}: {
  serverId: string;
  summary: PublisherSummary;
  listings: RegistryToolListing[];
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const toolCount = useMemo(() => listings.length, [listings]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{
          minHeight: 40,
          "& .MuiTab-root": { minHeight: 40 },
          "& .MuiTabs-indicator": { bgcolor: "var(--app-accent)" },
        }}
      >
        <Tab value="overview" label="Overview" />
        <Tab value="tools" label="Tools" />
      </Tabs>

      {activeTab === "overview" ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 3 }}>
            <KeyValuePanel
              title="Server snapshot"
              entries={[
                { label: "server_id", value: serverId },
                { label: "display_name", value: summary.display_name ?? "—" },
                { label: "tools_count", value: toolCount.toString() },
              ]}
            />
            {summary.description ? (
              <Box sx={{ mt: 3 }}>
                <Typography sx={{ fontSize: 13, color: "var(--app-fg)" }}>
                  {summary.description}
                </Typography>
              </Box>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {activeTab === "tools" ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Tools exposed by this server
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            Tool inventory is sourced from the server&apos;s publisher profile in the registry backend.
          </Typography>

          <Box sx={{ mt: 3 }}>
            {listings.length === 0 ? (
              <EmptyState
                title="No tools loaded yet"
                message="Once the publisher has live verified tools, they will show up here."
              />
            ) : (
              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                {listings.map((tool) => (
                  <Link
                    key={tool.tool_name}
                    href={`/public/listings/${encodeURIComponent(tool.tool_name)}`}
                    legacyBehavior
                    passHref
                  >
                    <Box
                      component="a"
                      sx={{
                        textDecoration: "none",
                        display: "flex",
                        flexDirection: "column",
                        gap: 1.25,
                        borderRadius: 3,
                        border: "1px solid var(--app-border)",
                        bgcolor: "var(--app-control-bg)",
                        p: 2,
                        "&:hover": { borderColor: "var(--app-accent)" },
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontSize: 16, fontWeight: 700, color: "var(--app-fg)" }} noWrap>
                            {tool.display_name ?? tool.tool_name}
                          </Typography>
                          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }} noWrap>
                            {tool.tool_name}
                          </Typography>
                        </Box>
                        <CertificationBadge level={tool.certification_level} />
                      </Box>
                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" }}>
                        {tool.description ?? "No description provided."}
                      </Typography>
                    </Box>
                  </Link>
                ))}
              </Box>
            )}
          </Box>
          </CardContent>
        </Card>
      ) : null}

    </Box>
  );
}


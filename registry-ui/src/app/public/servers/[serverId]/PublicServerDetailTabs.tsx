"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Box, Button, Card, CardContent, Tab, Tabs, Typography } from "@mui/material";

import { CertificationBadge, EmptyState, KeyValuePanel } from "@/components/security";
import type { PublisherSummary, RegistryToolListing } from "@/lib/registryClient";

type TabKey = "overview" | "tools" | "governance" | "observability";

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
        <Tab value="governance" label="Governance" />
        <Tab value="observability" label="Observability" />
      </Tabs>

      {activeTab === "overview" ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <KeyValuePanel
              title="Server snapshot"
              entries={[
                { label: "server_id", value: serverId },
                { label: "display_name", value: summary.display_name ?? "—" },
                { label: "tools_count", value: toolCount.toString() },
                { label: "drift_status", value: "unknown (stub)" },
              ]}
            />
            <KeyValuePanel
              title="Governance defaults"
              entries={[
                { label: "Policy Kernel", value: "pending (stub)" },
                { label: "Contract Broker", value: "pending (stub)" },
                { label: "Consent Graph", value: "pending (stub)" },
                { label: "Ledger", value: "enabled (stub)" },
              ]}
            />
          </Box>

          <Box sx={{ mt: 2 }}>
            <EmptyState
              title="Next: attach governance + review drift"
              message="This view is backed by publisher inventory; Governance and drift will become real once the backend server binding layer is wired."
            />
          </Box>
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

      {activeTab === "governance" ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Governance association
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            Stub UI: visualize effective bindings (Policy, Contract, Ledger, Consent) for this server and its tools.
          </Typography>
          <Box sx={{ mt: 3, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <KeyValuePanel
              title="Effective controls"
              entries={[
                { label: "Policy Kernel", value: "inherited (stub)" },
                { label: "Contract Broker", value: "inherited (stub)" },
                { label: "Consent Graph", value: "inherited (stub)" },
                { label: "Ledger", value: "recording (stub)" },
              ]}
            />
            <KeyValuePanel
              title="Overrides"
              entries={[
                { label: "Policy overrides", value: "none (stub)" },
                { label: "Contract overrides", value: "none (stub)" },
                { label: "Tool-level quarantine", value: "—" },
                { label: "Pending approvals", value: "0" },
              ]}
            />
          </Box>
          </CardContent>
        </Card>
      ) : null}

      {activeTab === "observability" ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Observability stream
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            Stub UI: show access decision events and ledger integrity checks feeding Reflexive Core recommendations.
          </Typography>
          <Box sx={{ mt: 3 }}>
            <KeyValuePanel
              title="Reflexive Core (stub)"
              entries={[
                { label: "recommendations", value: "none yet" },
                { label: "alerts", value: "—" },
                { label: "learning_window", value: "rolling (stub)" },
                { label: "confidence", value: "0%" },
              ]}
            />
          </Box>
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );
}


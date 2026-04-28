"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Divider,
  TextField,
  Typography,
} from "@mui/material";

import type { PublisherSummary } from "@/lib/registryClient";

type Props = {
  servers: PublisherSummary[];
  basePath?: string;
  onboardHref?: string;
  toolsHref?: string;
  publicView?: boolean;
};

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replaceAll(/\p{Diacritic}+/gu, "")
    .trim();
}

function serverHaystack(server: PublisherSummary): string {
  return normalizeText(
    [server.publisher_id, server.display_name, server.summary, server.description]
      .filter(Boolean)
      .join(" "),
  );
}

export function ServersDirectory({
  servers,
  basePath = "/registry/servers",
  onboardHref,
  toolsHref,
  publicView = false,
}: Props) {
  const [query, setQuery] = useState("");
  const normalizedQuery = useMemo(() => normalizeText(query), [query]);

  const filtered = useMemo(() => {
    const results = normalizedQuery
      ? servers.filter((server) => serverHaystack(server).includes(normalizedQuery))
      : servers;

    return [...results].sort((a, b) => {
      const aTools = a.verified_tool_count ?? a.tool_count ?? a.listing_count ?? 0;
      const bTools = b.verified_tool_count ?? b.tool_count ?? b.listing_count ?? 0;
      if (aTools !== bTools) return bTools - aTools;
      return (a.display_name ?? a.publisher_id).localeCompare(b.display_name ?? b.publisher_id);
    });
  }, [servers, normalizedQuery]);

  const hasActiveFilters = normalizedQuery.length > 0;

  return (
    <Card variant="outlined" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        <Box
          sx={{
            p: { xs: 2.5, md: 3 },
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            alignItems: { xs: "flex-start", md: "center" },
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          <Box sx={{ display: "grid", gap: 0.75, maxWidth: 720 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Server inventory
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              {servers.length
                ? `${servers.length} visible MCP ${servers.length === 1 ? "server" : "servers"}`
                : "No MCP servers visible yet"}
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {servers.length
                ? "Inspect publisher-backed MCP server sources and the tools they expose."
                : publicView
                  ? "Server profiles appear here after publishers have approved tools in the registry."
                  : "Onboard a real MCP server or approve publisher listings to create server profiles."}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {onboardHref ? (
              <Button component={Link} href={onboardHref} variant="contained">
                Onboard MCP server
              </Button>
            ) : null}
            {toolsHref ? (
              <Button component={Link} href={toolsHref} variant={onboardHref ? "outlined" : "contained"}>
                Trusted tools
              </Button>
            ) : null}
          </Box>
        </Box>

        {servers.length === 0 ? (
          <Box sx={{ px: { xs: 2.5, md: 3 }, pb: { xs: 2.5, md: 3 } }}>
            <Box
              sx={{
                p: { xs: 2.5, md: 3 },
                borderRadius: 3,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                display: "grid",
                gap: 1.5,
              }}
            >
              <Chip
                label="Server onboarding ready"
                size="small"
                sx={{ justifySelf: "start", bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" }}
              />
              <Typography sx={{ fontSize: 15, fontWeight: 700, color: "var(--app-fg)" }}>
                Start from a real MCP server source.
              </Typography>
              <Typography sx={{ maxWidth: 680, fontSize: 13, color: "var(--app-muted)" }}>
                Server profiles should reflect real publishers and approved tools. Once a server is onboarded and its
                tools are reviewed, it becomes available for inspection here.
              </Typography>
            </Box>
          </Box>
        ) : (
          <>
            <Divider />
            <Box sx={{ p: { xs: 2, md: 2.5 }, bgcolor: "var(--app-control-bg)" }}>
              <Box sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 1.25, alignItems: { md: "center" } }}>
                <TextField
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search servers by name, summary, or id..."
                  size="small"
                  fullWidth
                />
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  {hasActiveFilters ? (
                    <Button
                      type="button"
                      variant="outlined"
                      onClick={() => setQuery("")}
                      sx={{ borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                    >
                      Clear
                    </Button>
                  ) : null}
                  <Typography sx={{ whiteSpace: "nowrap", fontSize: 12, color: "var(--app-muted)" }}>
                    {filtered.length} result{filtered.length === 1 ? "" : "s"}
                  </Typography>
                </Box>
              </Box>
            </Box>

            <Divider />
            <Box sx={{ p: { xs: 2, md: 2.5 } }}>
              {filtered.length === 0 ? (
                <Box sx={{ p: 3, borderRadius: 3, border: "1px dashed var(--app-border)", textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>No matching servers</Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
                    Try clearing search or using a shorter term.
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                  {filtered.map((server) => {
                    const toolCount =
                      server.verified_tool_count ??
                      server.tool_count ??
                      server.listing_count ??
                      0;
                    return (
                      <Card key={server.publisher_id} variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                        <CardActionArea component={Link} href={`${basePath}/${encodeURIComponent(server.publisher_id)}`} sx={{ height: "100%" }}>
                          <CardContent sx={{ p: 2, display: "grid", gap: 1.25, minHeight: 148 }}>
                            <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
                              <Box sx={{ minWidth: 0 }}>
                                <Typography noWrap sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                                  {server.display_name ?? server.publisher_id}
                                </Typography>
                                <Typography noWrap sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                                  {server.publisher_id}
                                </Typography>
                              </Box>
                              {server.trust_score?.overall != null ? (
                                <Chip
                                  size="small"
                                  label={`Trust ${server.trust_score.overall.toFixed(1)}`}
                                  sx={{
                                    bgcolor: "var(--app-surface)",
                                    color: "var(--app-muted)",
                                    fontWeight: 700,
                                    fontSize: 11,
                                  }}
                                />
                              ) : null}
                            </Box>

                            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
                              {server.summary ?? server.description ?? "No server summary provided."}
                            </Typography>

                            <Typography sx={{ mt: "auto", fontSize: 12, color: "var(--app-muted)" }}>
                              {toolCount} approved {toolCount === 1 ? "tool" : "tools"} exposed
                            </Typography>
                          </CardContent>
                        </CardActionArea>
                      </Card>
                    );
                  })}
                </Box>
              )}
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
}

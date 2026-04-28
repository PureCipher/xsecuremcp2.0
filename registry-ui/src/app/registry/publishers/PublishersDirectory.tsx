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
  publishers: PublisherSummary[];
  basePath?: string;
  toolsHref?: string;
  publishHref?: string;
  publicView?: boolean;
};

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replaceAll(/\p{Diacritic}+/gu, "")
    .trim();
}

function publisherHaystack(publisher: PublisherSummary): string {
  return normalizeText(
    [
      publisher.publisher_id,
      publisher.display_name,
      publisher.summary,
      publisher.description,
    ]
      .filter(Boolean)
      .join(" "),
  );
}

export function PublishersDirectory({
  publishers,
  basePath = "/registry/publishers",
  toolsHref,
  publishHref,
  publicView = false,
}: Props) {
  const [query, setQuery] = useState("");
  const normalizedQuery = useMemo(() => normalizeText(query), [query]);

  const filtered = useMemo(() => {
    const results = normalizedQuery
      ? publishers.filter((publisher) => publisherHaystack(publisher).includes(normalizedQuery))
      : publishers;

    return [...results].sort((a, b) => {
      const aTrust = a.trust_score?.overall ?? -1;
      const bTrust = b.trust_score?.overall ?? -1;
      if (aTrust !== bTrust) return bTrust - aTrust;
      return (a.display_name ?? a.publisher_id).localeCompare(b.display_name ?? b.publisher_id);
    });
  }, [publishers, normalizedQuery]);

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
              Publisher network
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              {publishers.length
                ? `${publishers.length} active ${publishers.length === 1 ? "publisher" : "publishers"}`
                : "No active publishers yet"}
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {publishers.length
                ? "Review the people and teams behind approved registry listings."
                : publicView
                  ? "Publishers appear here after their tools are approved into the trusted directory."
                  : "Publisher profiles are created from real tool submissions that pass review."}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {publishHref ? (
              <Button component={Link} href={publishHref} variant="contained">
                Publish a tool
              </Button>
            ) : null}
            {toolsHref ? (
              <Button component={Link} href={toolsHref} variant={publishHref ? "outlined" : "contained"}>
                Trusted tools
              </Button>
            ) : null}
          </Box>
        </Box>

        {publishers.length === 0 ? (
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
                label="Publisher pipeline ready"
                size="small"
                sx={{ justifySelf: "start", bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" }}
              />
              <Typography sx={{ fontSize: 15, fontWeight: 700, color: "var(--app-fg)" }}>
                Profiles will appear from real approved listings.
              </Typography>
              <Typography sx={{ maxWidth: 680, fontSize: 13, color: "var(--app-muted)" }}>
                Once a publisher submits a tool and a reviewer approves it, their profile becomes visible here with trust
                score and listing counts.
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
                  placeholder="Search publishers by name, summary, or id..."
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
                  <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                    No matching publishers
                  </Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
                    Try clearing search or using a shorter term.
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                  {filtered.map((publisher) => (
                    <Card key={publisher.publisher_id} variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                      <CardActionArea component={Link} href={`${basePath}/${encodeURIComponent(publisher.publisher_id)}`} sx={{ height: "100%" }}>
                        <CardContent sx={{ p: 2, display: "grid", gap: 1.25, minHeight: 148 }}>
                          <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
                            <Box sx={{ minWidth: 0 }}>
                              <Typography noWrap sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                                {publisher.display_name ?? publisher.publisher_id}
                              </Typography>
                              <Typography noWrap sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                                {publisher.publisher_id}
                              </Typography>
                            </Box>
                            {publisher.trust_score?.overall != null ? (
                              <Chip
                                size="small"
                                label={`Trust ${publisher.trust_score.overall.toFixed(1)}`}
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
                            {publisher.summary ?? publisher.description ?? "No summary provided."}
                          </Typography>

                          <Typography sx={{ mt: "auto", fontSize: 12, color: "var(--app-muted)" }}>
                            {publisher.verified_tool_count ?? publisher.tool_count ?? publisher.listing_count ?? 0} approved{" "}
                            {(publisher.verified_tool_count ?? publisher.tool_count ?? publisher.listing_count ?? 0) === 1 ? "tool" : "tools"}
                          </Typography>
                        </CardContent>
                      </CardActionArea>
                    </Card>
                  ))}
                </Box>
              )}
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
}

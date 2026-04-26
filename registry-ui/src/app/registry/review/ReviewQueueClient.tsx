"use client";

import { useEffect, useMemo, useState } from "react";

import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  TextField,
  Typography,
} from "@mui/material";

import { CertificationBadge } from "@/components/security";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";
import type { ReviewQueueItem } from "@/lib/registryClient";
import { ReviewActions } from "./ReviewActions";

type Props = {
  sections: Record<string, ReviewQueueItem[]>;
};

type TabId = "pending_review" | "published" | "suspended" | "all";

function sectionLabel(key: string): string {
  if (key === "pending_review") return "Waiting for approval";
  if (key === "published") return "Live tools";
  if (key === "suspended") return "Paused tools";
  return key;
}

const TAB_ORDER: TabId[] = ["pending_review", "published", "suspended", "all"];

export function ReviewQueueClient({ sections }: Props) {
  const { prefs } = useRegistryUserPreferences();
  const [tab, setTab] = useState<TabId>("pending_review");
  const [tabTouched, setTabTouched] = useState(false);
  const [query, setQuery] = useState("");

  const normalizedQuery = query.trim().toLowerCase();
  const preferredTab = mapReviewerLaneToTab(prefs.reviewer.defaultLane);

  useEffect(() => {
    if (!tabTouched) setTab(preferredTab);
  }, [preferredTab, tabTouched]);

  const filteredSections = useMemo(() => {
    const base: Record<string, ReviewQueueItem[]> = {};
    const keys = ["pending_review", "published", "suspended"];

    const matches = (item: ReviewQueueItem) => {
      if (!normalizedQuery) return true;
      const hay = `${item.display_name ?? ""} ${item.tool_name ?? ""} ${item.description ?? ""} ${item.version ?? ""}`
        .toLowerCase()
        .trim();
      return hay.includes(normalizedQuery);
    };

    for (const key of keys) {
      const items = (sections[key] ?? []).filter(matches);
      base[key] = prefs.reviewer.highRiskFirst
        ? [...items].sort((a, b) => reviewRiskWeight(b) - reviewRiskWeight(a))
        : items;
    }

    return base;
  }, [sections, normalizedQuery, prefs.reviewer.highRiskFirst]);

  const counts = useMemo(() => {
    const pending = filteredSections.pending_review?.length ?? 0;
    const published = filteredSections.published?.length ?? 0;
    const suspended = filteredSections.suspended?.length ?? 0;
    return {
      pending_review: pending,
      published,
      suspended,
      all: pending + published + suspended,
    };
  }, [filteredSections]);

  const totalCounts = useMemo(() => {
    const pending = sections.pending_review?.length ?? 0;
    const published = sections.published?.length ?? 0;
    const suspended = sections.suspended?.length ?? 0;
    return {
      pending_review: pending,
      published,
      suspended,
      all: pending + published + suspended,
    };
  }, [sections]);

  const visibleKeys = useMemo(() => {
    if (tab === "all") return ["pending_review", "published", "suspended"];
    return [tab];
  }, [tab]);

  const hasActiveFilters = normalizedQuery.length > 0;
  const totalItems = totalCounts.all;
  const visibleTotal = visibleKeys.reduce((sum, key) => sum + (filteredSections[key]?.length ?? 0), 0);

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
              Moderation lanes
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              {totalItems ? `${totalItems} listing${totalItems === 1 ? "" : "s"} in review scope` : "No submissions waiting"}
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {totalItems
                ? "Review publisher submissions, pause risky listings, and keep the trusted directory clean."
                : "Real publisher submissions will appear here after preflight. Approved tools publish into the Trusted Tool Directory."}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            <Chip
              label={`${totalCounts.pending_review} waiting`}
              sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700 }}
            />
            <Chip
              label={`${totalCounts.published} live`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }}
            />
            <Chip
              label={`${totalCounts.suspended} paused`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }}
            />
          </Box>
        </Box>

        {totalItems === 0 ? (
          <Box sx={{ px: { xs: 2.5, md: 3 }, pb: { xs: 2.5, md: 3 } }}>
            <Box
              sx={{
                p: { xs: 2.5, md: 3 },
                borderRadius: 3,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                display: "grid",
                gap: 2,
              }}
            >
              <Box sx={{ display: "grid", gap: 0.75 }}>
                <Chip
                  label="Approval pipeline ready"
                  size="small"
                  sx={{ justifySelf: "start", bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" }}
                />
                <Typography sx={{ fontSize: 15, fontWeight: 700, color: "var(--app-fg)" }}>
                  Wait for real publisher submissions.
                </Typography>
                <Typography sx={{ maxWidth: 700, fontSize: 13, color: "var(--app-muted)" }}>
                  The queue is intentionally empty. Publishers should submit real tools through preflight, then reviewers
                  approve, request changes, reject, or suspend listings from this workspace.
                </Typography>
              </Box>

              <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
                {["Publisher submits", "Reviewer decides", "Directory updates"].map((label, index) => (
                  <Box
                    key={label}
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      border: "1px solid var(--app-border)",
                      bgcolor: "var(--app-surface)",
                    }}
                  >
                    <Typography sx={{ fontSize: 11, fontWeight: 700, color: "var(--app-muted)" }}>
                      Step {index + 1}
                    </Typography>
                    <Typography sx={{ mt: 0.25, fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                      {label}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        ) : (
          <>
            <Divider />
            <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 1.5, bgcolor: "var(--app-control-bg)" }}>
              <Box sx={{ display: "flex", flexDirection: { xs: "column", lg: "row" }, gap: 1.25, alignItems: { lg: "center" } }}>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {TAB_ORDER.map((id) => {
                    const selected = tab === id;
                    return (
                      <Button
                        key={id}
                        type="button"
                        variant={selected ? "contained" : "outlined"}
                        onClick={() => {
                          setTabTouched(true);
                          setTab(id);
                        }}
                        sx={{
                          bgcolor: selected ? "var(--app-accent)" : "var(--app-surface)",
                          color: selected ? "var(--app-accent-contrast)" : "var(--app-muted)",
                          borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
                          "&:hover": {
                            bgcolor: selected ? "var(--app-accent)" : "var(--app-hover-bg)",
                            borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
                          },
                        }}
                      >
                        {id === "all" ? "All" : sectionLabel(id)} ({counts[id]})
                      </Button>
                    );
                  })}
                </Box>

                <Box sx={{ flex: 1 }} />

                <Box sx={{ display: "flex", gap: 1, width: { xs: "100%", lg: "auto" } }}>
                  <TextField
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search tools..."
                    size="small"
                    sx={{ width: { xs: "100%", lg: 320 } }}
                  />
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
                </Box>
              </Box>
            </Box>

            <Divider />
            <Box sx={{ p: { xs: 2, md: 2.5 } }}>
              {visibleTotal === 0 ? (
                <Box sx={{ p: 3, borderRadius: 3, border: "1px dashed var(--app-border)", textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                    Nothing matches this view
                  </Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
                    Try another lane or clear search.
                  </Typography>
                </Box>
              ) : (
                <Box
                  component="section"
                  sx={{
                    display: "grid",
                    gap: 2,
                    gridTemplateColumns: { xs: "1fr", lg: tab === "all" ? "repeat(3, minmax(0, 1fr))" : "1fr" },
                  }}
                >
                  {visibleKeys.map((key) => {
                    const items = filteredSections[key] ?? [];
                    if (tab === "all" && items.length === 0) return null;
                    return (
                      <Box key={key} sx={{ display: "grid", gap: 1.5, alignContent: "start" }}>
                        <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 1 }}>
                          <Box>
                            <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                              {sectionLabel(key)}
                            </Typography>
                            <Typography sx={{ mt: 0.35, fontSize: 12, color: "var(--app-muted)" }}>
                              {items.length} listing{items.length === 1 ? "" : "s"}
                            </Typography>
                          </Box>
                        </Box>

                        {items.map((item) => <QueueCard key={item.listing_id} item={item} />)}
                      </Box>
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

function mapReviewerLaneToTab(lane: "pending" | "approved" | "rejected"): TabId {
  if (lane === "approved") return "published";
  if (lane === "rejected") return "suspended";
  return "pending_review";
}

function reviewRiskWeight(item: ReviewQueueItem): number {
  const level = String(item.certification_level ?? "").toLowerCase();
  const certificationWeight = level === "basic" ? 3 : level === "standard" ? 2 : level === "advanced" ? 1 : 0;
  const trustScore = typeof item.trust_score === "number" ? item.trust_score : 1;
  const trustWeight = Math.max(0, 1 - trustScore);
  const moderationWeight = Array.isArray(item.moderation_log) && item.moderation_log.length > 0 ? 0.5 : 0;
  return certificationWeight + trustWeight + moderationWeight;
}

function QueueCard({ item }: { item: ReviewQueueItem }) {
  const log = Array.isArray(item.moderation_log)
    ? item.moderation_log[item.moderation_log.length - 1]
    : null;
  const reason = log?.reason ?? "";
  return (
    <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
      <CardContent sx={{ p: 2 }}>
        <Box sx={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
              {item.display_name ?? item.tool_name}
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
              {item.tool_name} · {item.version}
            </Typography>
          </Box>
          <CertificationBadge level={item.certification_level} />
        </Box>
        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
          {item.description ?? "No description provided."}
        </Typography>
        {log ? (
          <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>
            Last decision:{" "}
            <Box component="span" sx={{ fontWeight: 700 }}>
              {log.action}
            </Box>{" "}
            by <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>{log.moderator_id}</Box>
            {reason ? (
              <>
                {" "}
                — {reason.slice(0, 80)}
                {reason.length > 80 ? "…" : ""}
              </>
            ) : null}
          </Typography>
        ) : null}
        <ReviewActions listingId={item.listing_id} availableActions={item.available_actions ?? []} />
      </CardContent>
    </Card>
  );
}


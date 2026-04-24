"use client";

import { useMemo, useState } from "react";

import {
  Badge,
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import { CertificationBadge } from "@/components/security";
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
  const [tab, setTab] = useState<TabId>("pending_review");
  const [query, setQuery] = useState("");

  const normalizedQuery = query.trim().toLowerCase();

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
      base[key] = (sections[key] ?? []).filter(matches);
    }

    return base;
  }, [sections, normalizedQuery]);

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

  const visibleKeys = useMemo(() => {
    if (tab === "all") return ["pending_review", "published", "suspended"];
    return [tab];
  }, [tab]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Card
        variant="outlined"
        sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}
      >
        <CardContent
          sx={{
            p: 2,
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
            alignItems: { sm: "center" },
            justifyContent: "space-between",
          }}
        >
          <ToggleButtonGroup
            exclusive
            value={tab}
            onChange={(_, next: TabId | null) => {
              if (next) setTab(next);
            }}
            sx={{
              flexWrap: "wrap",
              gap: 1,
              "& .MuiToggleButton-root": {
                borderRadius: 999,
                border: "1px solid var(--app-control-border) !important",
                bgcolor: "var(--app-control-bg)",
                color: "var(--app-muted)",
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                px: 1.5,
                py: 0.75,
              },
              "& .Mui-selected": {
                borderColor: "var(--app-accent) !important",
                bgcolor: "var(--app-control-active-bg)",
                color: "var(--app-fg)",
              },
            }}
          >
            {TAB_ORDER.map((id) => (
              <ToggleButton key={id} value={id}>
                <Badge
                  badgeContent={counts[id]}
                  color="primary"
                  sx={{
                    "& .MuiBadge-badge": {
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      fontSize: 9,
                      fontWeight: 800,
                    },
                  }}
                >
                  <span>{id === "all" ? "All" : sectionLabel(id)}</span>
                </Badge>
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          <Box sx={{ display: "flex", gap: 1, width: { xs: "100%", sm: "auto" } }}>
            <TextField
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tools…"
              size="small"
              sx={{ width: { xs: "100%", sm: 320 } }}
            />
            {query ? (
              <Button
                type="button"
                variant="outlined"
                onClick={() => setQuery("")}
                sx={{
                  borderRadius: 999,
                  borderColor: "var(--app-control-border)",
                  color: "var(--app-muted)",
                  bgcolor: "var(--app-control-bg)",
                  "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
                }}
              >
                Clear
              </Button>
            ) : null}
          </Box>
        </CardContent>
      </Card>

      <Box
        component="section"
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: tab === "all" ? "repeat(3, minmax(0, 1fr))" : "1fr" },
        }}
      >
        {visibleKeys.map((key) => {
          const items = filteredSections[key] ?? [];
          return (
            <Card
              key={key}
              variant="outlined"
              sx={{
                minHeight: 240,
                borderRadius: 4,
                borderColor: "var(--app-border)",
                bgcolor: "var(--app-surface)",
                boxShadow: "none",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <CardContent sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.5, flex: 1, minHeight: 0 }}>
                <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 1 }}>
                  <Box>
                    <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                      {sectionLabel(key)}
                    </Typography>
                    <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                      {items.length} listing{items.length === 1 ? "" : "s"}
                    </Typography>
                  </Box>
                  {tab !== "all" ? (
                    <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                      Showing{" "}
                      <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                        {sectionLabel(key)}
                      </Box>
                    </Typography>
                  ) : null}
                </Box>

                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, overflow: "auto", flex: 1, pr: 0.5 }}>
                  {items.length === 0 ? (
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>Nothing in this lane right now.</Typography>
                  ) : (
                    items.map((item) => <QueueCard key={item.listing_id} item={item} />)
                  )}
                </Box>
              </CardContent>
            </Card>
          );
        })}
      </Box>
    </Box>
  );
}

function QueueCard({ item }: { item: ReviewQueueItem }) {
  const log = Array.isArray(item.moderation_log)
    ? item.moderation_log[item.moderation_log.length - 1]
    : null;
  const reason = log?.reason ?? "";
  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        boxShadow: "none",
      }}
    >
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


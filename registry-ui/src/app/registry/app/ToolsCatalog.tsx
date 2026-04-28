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
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";

import { AttestationBadge } from "@/components/security";
import type { RegistryToolListing } from "@/lib/registryClient";

type SortMode = "certification_desc" | "name_asc";

type Props = {
  tools: RegistryToolListing[];
  basePath?: string;
  publishHref?: string;
  reviewHref?: string;
  publishersHref?: string;
  pendingCount?: number;
  publicView?: boolean;
  initialQuery?: string;
  hideSummary?: boolean;
};

type CertificationInfo = {
  raw: string | null;
  label: string;
  tier: number;
  sx: Record<string, unknown>;
};

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replaceAll(/\p{Diacritic}+/gu, "")
    .trim();
}

function certificationInfo(level?: string): CertificationInfo {
  const raw = level?.trim() ? level.trim() : null;
  const upper = raw?.toUpperCase?.() ?? "";

  if (!raw || upper === "UNRATED" || upper === "NONE" || upper === "UNKNOWN") {
    return {
      raw,
      label: "Unrated",
      tier: 0,
      sx: { bgcolor: "rgba(100, 116, 139, 0.12)", color: "var(--app-muted)" },
    };
  }

  if (upper.includes("CERTIFIED") || upper.includes("VERIFIED") || upper.includes("TRUSTED")) {
    return {
      raw,
      label: raw,
      tier: 3,
      sx: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
    };
  }

  if (upper.includes("ATTEST") || upper.includes("SIGNED")) {
    return {
      raw,
      label: raw,
      tier: 2,
      sx: { bgcolor: "rgba(14, 165, 233, 0.12)", color: "#0369a1" },
    };
  }

  return {
    raw,
    label: raw,
    tier: 1,
    sx: { bgcolor: "var(--app-surface)", color: "var(--app-fg)" },
  };
}

function toolSearchHaystack(tool: RegistryToolListing): string {
  const parts: string[] = [];
  if (tool.display_name) parts.push(tool.display_name);
  if (tool.tool_name) parts.push(tool.tool_name);
  if (tool.description) parts.push(tool.description);
  if (Array.isArray(tool.categories) && tool.categories.length > 0) {
    parts.push(tool.categories.join(" "));
  }
  if (tool.publisher_id) parts.push(tool.publisher_id);
  return normalizeText(parts.join(" "));
}

export function ToolsCatalog({
  tools,
  basePath = "/registry/listings",
  publishHref,
  reviewHref,
  publishersHref,
  pendingCount = 0,
  publicView = false,
  initialQuery = "",
  hideSummary = false,
}: Props) {
  const [query, setQuery] = useState(initialQuery);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("certification_desc");
  const [attestationFilter, setAttestationFilter] = useState<
    "all" | "author" | "curator"
  >("all");

  const allCategories = useMemo(() => {
    const bag = new Set<string>();
    for (const tool of tools) {
      if (!Array.isArray(tool.categories)) continue;
      for (const cat of tool.categories) {
        const trimmed = (cat ?? "").trim();
        if (trimmed) bag.add(trimmed);
      }
    }
    return Array.from(bag).sort((a, b) => a.localeCompare(b));
  }, [tools]);

  const normalizedQuery = useMemo(() => normalizeText(query), [query]);

  const hasCuratedListings = useMemo(
    () => tools.some((t) => t.attestation_kind === "curator"),
    [tools],
  );
  const hasAuthorListings = useMemo(
    () =>
      tools.some(
        (t) =>
          !t.attestation_kind || t.attestation_kind === "author",
      ),
    [tools],
  );
  const showAttestationFilter = hasCuratedListings && hasAuthorListings;

  const filtered = useMemo(() => {
    const activeCategories = new Set(selectedCategories);
    const hasQuery = normalizedQuery.length > 0;
    const hasCategories = activeCategories.size > 0;

    const results: RegistryToolListing[] = [];
    for (const tool of tools) {
      if (hasCategories) {
        const cats = Array.isArray(tool.categories) ? tool.categories : [];
        const matches = cats.some((c) => activeCategories.has(String(c)));
        if (!matches) continue;
      }
      if (hasQuery) {
        const hay = toolSearchHaystack(tool);
        if (!hay.includes(normalizedQuery)) continue;
      }
      if (attestationFilter !== "all") {
        const kind =
          tool.attestation_kind === "curator" ? "curator" : "author";
        if (kind !== attestationFilter) continue;
      }
      results.push(tool);
    }

    results.sort((a, b) => {
      if (sortMode === "name_asc") {
        const aName = a.display_name ?? a.tool_name;
        const bName = b.display_name ?? b.tool_name;
        return aName.localeCompare(bName);
      }

      const aCert = certificationInfo(a.certification_level);
      const bCert = certificationInfo(b.certification_level);
      if (aCert.tier !== bCert.tier) return bCert.tier - aCert.tier;

      const aName = a.display_name ?? a.tool_name;
      const bName = b.display_name ?? b.tool_name;
      return aName.localeCompare(bName);
    });

    return results;
  }, [tools, normalizedQuery, selectedCategories, sortMode, attestationFilter]);

  const hasActiveFilters =
    normalizedQuery.length > 0 ||
    selectedCategories.length > 0 ||
    attestationFilter !== "all";

  return (
    <Card variant="outlined" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        {!hideSummary ? (
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
                Directory
              </Typography>
              <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
                {tools.length ? `${tools.length} trusted ${tools.length === 1 ? "tool" : "tools"}` : "No trusted tools yet"}
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                {tools.length
                  ? "Browse approved tools that passed certification and review."
                  : publicView
                    ? "Approved tools will appear here once publishers submit them and reviewers approve them."
                    : "Publish a real tool, run preflight, and send it to review. Approved listings appear here automatically."}
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              {publishHref ? (
                <Button component={Link} href={publishHref} variant="contained">
                  Publish a tool
                </Button>
              ) : null}
              {reviewHref ? (
                <Button component={Link} href={reviewHref} variant="outlined" sx={{ borderColor: "var(--app-accent)", color: "var(--app-muted)" }}>
                  Review queue{pendingCount ? ` (${pendingCount})` : ""}
                </Button>
              ) : null}
              {publishersHref ? (
                <Button component={Link} href={publishersHref} variant={publishHref || reviewHref ? "outlined" : "contained"}>
                  Browse publishers
                </Button>
              ) : null}
            </Box>
          </Box>
        ) : null}

        {tools.length === 0 ? (
          <Box
            sx={{
              px: { xs: 2.5, md: 3 },
              pt: hideSummary ? { xs: 2.5, md: 3 } : undefined,
              pb: { xs: 2.5, md: 3 },
            }}
          >
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
                  Start with a real publisher submission.
                </Typography>
                <Typography sx={{ maxWidth: 680, fontSize: 13, color: "var(--app-muted)" }}>
                  The directory is intentionally empty now. Tools should enter through publisher preflight, reviewer approval,
                  and then publication into this trusted catalog.
                </Typography>
              </Box>

              {!publicView ? (
                <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
                  {["Submit from Publisher", "Review and approve", "Publish to directory"].map((label, index) => (
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
              ) : null}
            </Box>
          </Box>
        ) : (
          <>
            {!hideSummary ? <Divider /> : null}
            <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 1.5, bgcolor: "var(--app-control-bg)" }}>
              <Box sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 1.25, alignItems: { md: "center" } }}>
                <TextField
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by name, category, publisher..."
                  size="small"
                  fullWidth
                />

                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                  <FormControl size="small" sx={{ minWidth: 180 }}>
                    <InputLabel id="tool-sort">Sort</InputLabel>
                    <Select
                      labelId="tool-sort"
                      label="Sort"
                      value={sortMode}
                      onChange={(e) => setSortMode(e.target.value as SortMode)}
                    >
                      <MenuItem value="certification_desc">Certification</MenuItem>
                      <MenuItem value="name_asc">Name A-Z</MenuItem>
                    </Select>
                  </FormControl>

                  {hasActiveFilters ? (
                    <Button
                      type="button"
                      variant="outlined"
                      onClick={() => {
                        setQuery("");
                        setSelectedCategories([]);
                        setAttestationFilter("all");
                      }}
                      sx={{ borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                    >
                      Clear
                    </Button>
                  ) : null}

                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    {filtered.length} result{filtered.length === 1 ? "" : "s"}
                  </Typography>
                </Box>
              </Box>

              {allCategories.length > 0 ? (
                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Categories
                  </Typography>
                  {allCategories.map((cat) => {
                    const selected = selectedCategories.includes(cat);
                    return (
                      <Chip
                        key={cat}
                        label={cat}
                        clickable
                        onClick={() => {
                          setSelectedCategories((current) => {
                            if (current.includes(cat)) return current.filter((c) => c !== cat);
                            return [...current, cat];
                          });
                        }}
                        sx={{
                          bgcolor: selected ? "var(--app-control-active-bg)" : "var(--app-surface)",
                          color: selected ? "var(--app-fg)" : "var(--app-muted)",
                          border: "1px solid",
                          borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
                        }}
                      />
                    );
                  })}
                </Box>
              ) : null}

              {showAttestationFilter ? (
                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Attestation
                  </Typography>
                  {(["all", "author", "curator"] as const).map((value) => {
                    const selected = attestationFilter === value;
                    const labels = {
                      all: "All",
                      author: "Author-attested",
                      curator: "Curator-vouched",
                    };
                    return (
                      <Chip
                        key={value}
                        label={labels[value]}
                        clickable
                        onClick={() => setAttestationFilter(value)}
                        sx={{
                          bgcolor: selected ? "var(--app-control-active-bg)" : "var(--app-surface)",
                          color: selected ? "var(--app-fg)" : "var(--app-muted)",
                          border: "1px solid",
                          borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
                        }}
                      />
                    );
                  })}
                </Box>
              ) : null}
            </Box>

            <Divider />
            <Box sx={{ p: { xs: 2, md: 2.5 } }}>
              {filtered.length === 0 ? (
                <Box sx={{ p: 3, borderRadius: 3, border: "1px dashed var(--app-border)", textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>No matching tools</Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
                    Try clearing filters or searching by a shorter term.
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                  {filtered.map((tool) => {
                    const cert = certificationInfo(tool.certification_level);
                    return (
                      <Card
                        key={tool.tool_name}
                        variant="outlined"
                        sx={{
                          bgcolor: "var(--app-control-bg)",
                          "&:hover": { borderColor: "var(--app-accent)" },
                          display: "flex",
                          flexDirection: "column",
                        }}
                      >
                        <CardActionArea component={Link} href={`${basePath}/${encodeURIComponent(tool.tool_name)}`} sx={{ height: "100%" }}>
                          <CardContent sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.25, minHeight: 154 }}>
                            <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
                              <Box sx={{ minWidth: 0 }}>
                                <Typography noWrap sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                                  {tool.display_name ?? tool.tool_name}
                                </Typography>
                                <Typography noWrap sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                                  {tool.tool_name}
                                </Typography>
                              </Box>
                              <Chip
                                size="small"
                                label={cert.label}
                                title={cert.raw ?? "Unrated"}
                                sx={{
                                  ...cert.sx,
                                  fontSize: 11,
                                  fontWeight: 700,
                                  letterSpacing: "0.01em",
                                  height: 24,
                                }}
                              />
                            </Box>

                            {tool.attestation_kind === "curator" ? (
                              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                                <AttestationBadge
                                  kind="curator"
                                  curatorId={tool.curator_id}
                                />
                              </Box>
                            ) : null}

                            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
                              {tool.description ?? "No description provided."}
                            </Typography>

                            {Array.isArray(tool.categories) && tool.categories.length > 0 ? (
                              <Box sx={{ mt: "auto", pt: 1, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                                {tool.categories.slice(0, 4).map((cat: string) => (
                                  <Chip
                                    key={cat}
                                    size="small"
                                    label={cat}
                                    sx={{ bgcolor: "var(--app-surface)", color: "var(--app-fg)", fontSize: 11 }}
                                  />
                                ))}
                                {tool.categories.length > 4 ? (
                                  <Typography sx={{ alignSelf: "center", fontSize: 11, color: "var(--app-muted)" }}>
                                    +{tool.categories.length - 4}
                                  </Typography>
                                ) : null}
                              </Box>
                            ) : null}
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

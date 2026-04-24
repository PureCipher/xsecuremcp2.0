"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Box, Button, Card, CardActionArea, CardContent, Chip, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";

import type { RegistryToolListing } from "@/lib/registryClient";

type SortMode = "certification_desc" | "name_asc";

type Props = {
  tools: RegistryToolListing[];
  basePath?: string;
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
      sx: { bgcolor: "rgba(113, 113, 122, 0.12)", color: "rgb(228, 228, 231)" },
    };
  }

  // We don't have a fixed enum here; prefer a stable ordering heuristic that still
  // sorts "more certified" above "less certified" for common names.
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
      sx: { bgcolor: "rgba(14, 165, 233, 0.12)", color: "rgb(224, 242, 254)" },
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

export function ToolsCatalog({ tools, basePath = "/registry/listings" }: Props) {
  const [query, setQuery] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("certification_desc");

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
  }, [tools, normalizedQuery, selectedCategories, sortMode]);

  const hasActiveFilters = normalizedQuery.length > 0 || selectedCategories.length > 0;

  return (
    <Box sx={{ display: "grid", gap: 2 }}>
      <Card
        variant="outlined"
        sx={{
          borderRadius: 4,
          borderColor: "var(--app-border)",
          bgcolor: "var(--app-control-bg)",
          boxShadow: "none",
        }}
      >
        <CardContent sx={{ p: 2, display: "grid", gap: 2 }}>
          <Box sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 1.5, alignItems: { md: "center" } }}>
            <Box sx={{ flex: 1 }}>
              <TextField
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tools by name, description, category, publisher…"
                size="small"
                fullWidth
              />
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="tool-sort">Sort</InputLabel>
                <Select
                  labelId="tool-sort"
                  label="Sort"
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value as SortMode)}
                >
                  <MenuItem value="certification_desc">Certification</MenuItem>
                  <MenuItem value="name_asc">Name A→Z</MenuItem>
                </Select>
              </FormControl>

              {hasActiveFilters ? (
                <Button
                  type="button"
                  variant="outlined"
                  onClick={() => {
                    setQuery("");
                    setSelectedCategories([]);
                  }}
                  sx={{
                    borderRadius: 999,
                    borderColor: "var(--app-border)",
                    color: "var(--app-muted)",
                    bgcolor: "var(--app-control-bg)",
                    "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
                  }}
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
              <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Categories
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
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
                        borderRadius: 999,
                        bgcolor: selected ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                        color: selected ? "var(--app-fg)" : "var(--app-muted)",
                        border: "1px solid",
                        borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
                      }}
                    />
                  );
                })}
              </Box>
            </Box>
          ) : null}
        </CardContent>
      </Card>

      {filtered.length === 0 ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>No tools match your filters.</Typography>
            {hasActiveFilters ? (
              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                Try clearing filters or searching by a shorter term.
              </Typography>
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "1fr 1fr 1fr" } }}>
          {filtered.map((tool) => {
            const cert = certificationInfo(tool.certification_level);
            return (
              <Card
                key={tool.tool_name}
                variant="outlined"
                sx={{
                  borderRadius: 3,
                  borderColor: "var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  boxShadow: "none",
                  "&:hover": { borderColor: "var(--app-accent)" },
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <Link href={`${basePath}/${encodeURIComponent(tool.tool_name)}`} legacyBehavior passHref>
                  <CardActionArea component="a" sx={{ borderRadius: 3, height: "100%" }}>
                    <CardContent sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.25, flex: 1 }}>
                      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography noWrap sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                            {tool.display_name ?? tool.tool_name}
                          </Typography>
                          <Typography noWrap sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                            {tool.tool_name}
                          </Typography>
                        </Box>
                        <Chip
                          size="small"
                          label={cert.label}
                          title={cert.raw ?? "Unrated"}
                          sx={{
                            ...cert.sx,
                            borderRadius: 999,
                            fontSize: 10,
                            fontWeight: 800,
                            textTransform: "uppercase",
                            letterSpacing: "0.12em",
                            height: 22,
                          }}
                        />
                      </Box>

                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {tool.description ?? "No description provided."}
                      </Typography>

                      {Array.isArray(tool.categories) && tool.categories.length > 0 ? (
                        <Box sx={{ mt: "auto", pt: 1, display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                          {tool.categories.slice(0, 4).map((cat: string) => (
                            <Chip
                              key={cat}
                              size="small"
                              label={cat}
                              sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-fg)", fontSize: 11 }}
                            />
                          ))}
                          {tool.categories.length > 4 ? (
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>+{tool.categories.length - 4}</Typography>
                          ) : null}
                        </Box>
                      ) : (
                        <Typography sx={{ mt: "auto", pt: 1, fontSize: 11, color: "var(--app-muted)" }}>No categories</Typography>
                      )}
                    </CardContent>
                  </CardActionArea>
                </Link>
              </Card>
            );
          })}
        </Box>
      )}
    </Box>
  );
}


"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import type { PolicyBundleItem } from "@/lib/registryClient";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { BundleDetailDrawer } from "../BundleDetailDrawer";

type CatalogTabProps = {
  bundles: PolicyBundleItem[];
  onStageBundle: (bundleId: string, title: string) => Promise<void>;
};

/**
 * Iter 14.16 — Catalog tab.
 *
 * Lifted out of the legacy Overview tab as part of splitting two
 * different workflows that don't belong on the same page:
 *
 * - **Catalog** (this tab) is a *picking* activity — browse,
 *   compare, install policy bundles. Visual rhythm matches a
 *   product gallery: tiled layout (Iter 14.15), bundle detail
 *   drawer (Iter 14.12), Stage CTA on every tile.
 * - **Metrics** (sibling tab) is a *monitoring* activity — glance
 *   at deny rates, track trends, drill into history.
 *
 * Splitting them means a curator picking a bundle no longer
 * scrolls past the analytics dashboard, and an admin checking
 * metrics doesn't scroll past a catalog they aren't interested in.
 */
// Iter 14.19 — Search & filter helpers.
//
// Filter state lives in URL params so deep-links work
// (?q=stripe&risk=strict,balanced&env=production). The data-driven
// chip lists are computed from the loaded bundles, so a deployment
// with site-specific bundles (Iter 14.21) gets a search surface
// that reflects its actual catalog rather than a hardcoded set.

const _SEARCH_PARAM_QUERY = "q";
const _SEARCH_PARAM_RISK = "risk";
const _SEARCH_PARAM_ENV = "env";

function _parseCsvParam(value: string | null): Set<string> {
  if (!value) return new Set();
  return new Set(
    value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

function _matchesSearch(bundle: PolicyBundleItem, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  const haystack = [
    bundle.bundle_id,
    bundle.title ?? "",
    bundle.summary ?? "",
    bundle.description ?? "",
    ...(bundle.tags ?? []),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

export function CatalogTab({ bundles, onStageBundle }: CatalogTabProps) {
  const { busyKey } = usePolicyContext();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Iter 14.12 — bundle detail drawer state. The drawer is rendered
  // once at the bottom of this component; ``activeBundle`` controls
  // which bundle's payload it shows.
  const [activeBundle, setActiveBundle] = useState<PolicyBundleItem | null>(
    null,
  );

  // Iter 14.19 — filter state derived from URL params on every
  // render so back/forward + deep-links all work without a
  // separate sync effect.
  const queryRaw = searchParams?.get(_SEARCH_PARAM_QUERY) ?? "";
  const selectedRiskPostures = useMemo(
    () => _parseCsvParam(searchParams?.get(_SEARCH_PARAM_RISK) ?? null),
    [searchParams],
  );
  const selectedEnvironments = useMemo(
    () => _parseCsvParam(searchParams?.get(_SEARCH_PARAM_ENV) ?? null),
    [searchParams],
  );

  // Local search input mirror so typing feels snappy; URL update is
  // debounced via ``onBlur`` rather than per-keystroke. Pre-fills
  // from the URL on mount so deep-links populate the box.
  const [queryInput, setQueryInput] = useState(queryRaw);

  // Compute the data-driven chip lists once per bundle change. Sort
  // them so the order is stable across re-renders.
  const availableRiskPostures = useMemo(() => {
    const set = new Set<string>();
    for (const b of bundles) if (b.risk_posture) set.add(b.risk_posture);
    return Array.from(set).sort();
  }, [bundles]);
  const availableEnvironments = useMemo(() => {
    const set = new Set<string>();
    for (const b of bundles) {
      for (const env of b.recommended_environments ?? []) set.add(env);
    }
    return Array.from(set).sort();
  }, [bundles]);

  // The filtered list — applied in order: risk → env → search.
  // Each filter is a no-op when its constraint set is empty, so
  // an unconstrained user sees the full catalog.
  const filteredBundles = useMemo(() => {
    return bundles.filter((bundle) => {
      if (
        selectedRiskPostures.size > 0 &&
        !(bundle.risk_posture && selectedRiskPostures.has(bundle.risk_posture))
      ) {
        return false;
      }
      if (selectedEnvironments.size > 0) {
        const envs = bundle.recommended_environments ?? [];
        const matches = envs.some((e) => selectedEnvironments.has(e));
        if (!matches) return false;
      }
      if (!_matchesSearch(bundle, queryRaw)) return false;
      return true;
    });
  }, [bundles, selectedRiskPostures, selectedEnvironments, queryRaw]);

  const isFiltering =
    queryRaw.length > 0 ||
    selectedRiskPostures.size > 0 ||
    selectedEnvironments.size > 0;

  // Helpers to mutate the URL state. We use ``router.replace`` so
  // filter changes don't pollute back-button history with one entry
  // per chip click.
  const updateParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams?.toString() ?? "");
      mutate(next);
      const queryString = next.toString();
      router.replace(queryString ? `?${queryString}` : "?", {
        scroll: false,
      });
    },
    [router, searchParams],
  );

  const setQueryParam = useCallback(
    (value: string) => {
      updateParams((p) => {
        if (value) p.set(_SEARCH_PARAM_QUERY, value);
        else p.delete(_SEARCH_PARAM_QUERY);
      });
    },
    [updateParams],
  );

  const toggleSet = useCallback(
    (paramName: string, value: string) => {
      updateParams((p) => {
        const current = _parseCsvParam(p.get(paramName));
        if (current.has(value)) current.delete(value);
        else current.add(value);
        if (current.size === 0) p.delete(paramName);
        else p.set(paramName, Array.from(current).sort().join(","));
      });
    },
    [updateParams],
  );

  const clearAllFilters = useCallback(() => {
    setQueryInput("");
    updateParams((p) => {
      p.delete(_SEARCH_PARAM_QUERY);
      p.delete(_SEARCH_PARAM_RISK);
      p.delete(_SEARCH_PARAM_ENV);
    });
  }, [updateParams]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Card variant="outlined">
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Reusable bundles
            </Typography>
            <Typography
              variant="h5"
              sx={{ fontWeight: 700, color: "var(--app-fg)" }}
            >
              Start from proven policy packs
            </Typography>
            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
              Bundles stage full-chain proposals for common registry
              operating modes. Use the View details drawer to see
              every provider step before staging.
            </Typography>
          </Box>

          {/* Iter 14.19 — Search + filter row. Always visible above
              the gallery. Search input on the left, posture and env
              chip filters below. URL-backed so deep-links work. */}
          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            <Box
              sx={{
                display: "flex",
                gap: 1,
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
              <TextField
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                onBlur={() => setQueryParam(queryInput.trim())}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    setQueryParam(queryInput.trim());
                  }
                  if (e.key === "Escape") {
                    setQueryInput("");
                    setQueryParam("");
                  }
                }}
                placeholder={`Filter ${bundles.length} bundle${bundles.length === 1 ? "" : "s"} by name, summary, or tag…`}
                size="small"
                fullWidth
                slotProps={{
                  input: {
                    sx: { fontSize: 13 },
                    endAdornment: queryInput ? (
                      <Tooltip title="Clear search">
                        <IconButton
                          size="small"
                          onClick={() => {
                            setQueryInput("");
                            setQueryParam("");
                          }}
                          aria-label="Clear search"
                        >
                          <Box
                            component="svg"
                            width={14}
                            height={14}
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <line x1={18} y1={6} x2={6} y2={18} />
                            <line x1={6} y1={6} x2={18} y2={18} />
                          </Box>
                        </IconButton>
                      </Tooltip>
                    ) : null,
                  },
                }}
                sx={{ flex: 1, minWidth: 220 }}
              />
              {isFiltering ? (
                <Button
                  size="small"
                  variant="text"
                  onClick={clearAllFilters}
                  sx={{
                    textTransform: "none",
                    color: "var(--app-muted)",
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  Clear all
                </Button>
              ) : null}
            </Box>

            {availableRiskPostures.length > 0 ||
            availableEnvironments.length > 0 ? (
              <Box
                sx={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 2,
                  alignItems: "center",
                }}
              >
                {availableRiskPostures.length > 0 ? (
                  <Box
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 0.5,
                      alignItems: "center",
                    }}
                  >
                    <Typography
                      sx={{
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                        color: "var(--app-muted)",
                        mr: 0.5,
                      }}
                    >
                      Risk
                    </Typography>
                    {availableRiskPostures.map((posture) => {
                      const isOn = selectedRiskPostures.has(posture);
                      return (
                        <Chip
                          key={`risk-${posture}`}
                          label={posture}
                          size="small"
                          clickable
                          onClick={() => toggleSet(_SEARCH_PARAM_RISK, posture)}
                          sx={{
                            fontSize: 11,
                            fontWeight: 700,
                            letterSpacing: "0.01em",
                            bgcolor: isOn
                              ? "var(--app-control-active-bg)"
                              : "var(--app-surface)",
                            color: isOn
                              ? "var(--app-fg)"
                              : "var(--app-muted)",
                            border: "1px solid",
                            borderColor: isOn
                              ? "var(--app-accent)"
                              : "var(--app-border)",
                          }}
                        />
                      );
                    })}
                  </Box>
                ) : null}

                {availableEnvironments.length > 0 ? (
                  <Box
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 0.5,
                      alignItems: "center",
                    }}
                  >
                    <Typography
                      sx={{
                        fontSize: 11,
                        fontWeight: 700,
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                        color: "var(--app-muted)",
                        mr: 0.5,
                      }}
                    >
                      Environment
                    </Typography>
                    {availableEnvironments.map((env) => {
                      const isOn = selectedEnvironments.has(env);
                      return (
                        <Chip
                          key={`env-${env}`}
                          label={env}
                          size="small"
                          clickable
                          onClick={() => toggleSet(_SEARCH_PARAM_ENV, env)}
                          sx={{
                            fontSize: 11,
                            fontWeight: 700,
                            letterSpacing: "0.01em",
                            bgcolor: isOn
                              ? "var(--app-control-active-bg)"
                              : "var(--app-surface)",
                            color: isOn
                              ? "var(--app-fg)"
                              : "var(--app-muted)",
                            border: "1px solid",
                            borderColor: isOn
                              ? "var(--app-accent)"
                              : "var(--app-border)",
                          }}
                        />
                      );
                    })}
                  </Box>
                ) : null}

                {isFiltering ? (
                  <Typography
                    sx={{
                      fontSize: 12,
                      color: "var(--app-muted)",
                      ml: "auto",
                    }}
                  >
                    Showing <strong style={{ color: "var(--app-fg)" }}>{filteredBundles.length}</strong>{" "}
                    of {bundles.length}
                  </Typography>
                ) : null}
              </Box>
            ) : null}
          </Box>

          {/* Iter 14.15 — Tile gallery layout. Three tiles per row
              on wide screens, two on medium, one on narrow. */}
          <Box
            sx={{
              mt: 2,
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: {
                xs: "1fr",
                md: "repeat(2, minmax(0, 1fr))",
                xl: "repeat(3, minmax(0, 1fr))",
              },
              alignItems: "stretch",
            }}
          >
            {bundles.length === 0 ? (
              <Card
                variant="outlined"
                sx={{
                  bgcolor: "var(--app-control-bg)",
                  gridColumn: "1 / -1",
                }}
              >
                <CardContent sx={{ p: 2 }}>
                  <Typography
                    sx={{ fontSize: 12, color: "var(--app-muted)" }}
                  >
                    No reusable bundles are available yet.
                  </Typography>
                </CardContent>
              </Card>
            ) : filteredBundles.length === 0 ? (
              // Iter 14.19 — empty state for "you filtered to nothing"
              // is meaningfully different from "registry has no bundles":
              // here we offer a one-click escape hatch back to the
              // unfiltered catalog.
              <Card
                variant="outlined"
                sx={{
                  bgcolor: "var(--app-control-bg)",
                  gridColumn: "1 / -1",
                }}
              >
                <CardContent
                  sx={{
                    p: 2.5,
                    display: "flex",
                    alignItems: "center",
                    gap: 2,
                    flexWrap: "wrap",
                  }}
                >
                  <Box>
                    <Typography
                      sx={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: "var(--app-fg)",
                      }}
                    >
                      No bundles match your filters
                    </Typography>
                    <Typography
                      sx={{ fontSize: 12, color: "var(--app-muted)", mt: 0.5 }}
                    >
                      Try removing a chip filter or clearing the search.
                    </Typography>
                  </Box>
                  <Button
                    onClick={clearAllFilters}
                    variant="outlined"
                    size="small"
                    sx={{
                      textTransform: "none",
                      ml: "auto",
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                    }}
                  >
                    Clear all filters
                  </Button>
                </CardContent>
              </Card>
            ) : (
              filteredBundles.map((bundle) => {
                const summaries = bundle.provider_summaries ?? [];
                const totalSteps =
                  summaries.length || (bundle.provider_count ?? 0);
                const previewSteps = summaries.slice(0, 2);
                const remaining = Math.max(
                  0,
                  summaries.length - previewSteps.length,
                );
                const stageBusy = busyKey === `bundle-${bundle.bundle_id}`;
                const environments = bundle.recommended_environments ?? [];
                return (
                  <Card
                    key={bundle.bundle_id}
                    variant="outlined"
                    sx={{
                      bgcolor: "var(--app-control-bg)",
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      transition:
                        "border-color 120ms ease, transform 120ms ease",
                      "&:hover": { borderColor: "var(--app-accent)" },
                    }}
                  >
                    <CardContent
                      sx={{
                        p: 2,
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        gap: 1.25,
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: 1,
                        }}
                      >
                        <Typography
                          sx={{
                            fontSize: 14,
                            fontWeight: 800,
                            color: "var(--app-fg)",
                            lineHeight: 1.3,
                            wordBreak: "break-word",
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          {bundle.title ?? bundle.bundle_id}
                        </Typography>
                        {bundle.risk_posture ? (
                          <Chip
                            size="small"
                            label={bundle.risk_posture}
                            sx={{
                              flexShrink: 0,
                              bgcolor: "var(--app-surface)",
                              color: "var(--app-muted)",
                              fontSize: 10,
                              fontWeight: 700,
                              letterSpacing: "0.01em",
                              height: 22,
                            }}
                          />
                        ) : null}
                      </Box>

                      <Typography
                        sx={{
                          fontSize: 12.5,
                          color: "var(--app-muted)",
                          lineHeight: 1.5,
                          display: "-webkit-box",
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {bundle.summary ?? bundle.description}
                      </Typography>

                      {previewSteps.length > 0 ? (
                        <Box
                          component="ul"
                          sx={{
                            listStyle: "disc",
                            pl: 2,
                            m: 0,
                            color: "var(--app-muted)",
                            fontSize: 11,
                            display: "grid",
                            gap: 0.4,
                            "& li::marker": { color: "var(--app-accent)" },
                          }}
                        >
                          {previewSteps.map((line, index) => (
                            <Box
                              component="li"
                              key={`${bundle.bundle_id}-step-${index}`}
                              sx={{
                                display: "-webkit-box",
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: "vertical",
                                overflow: "hidden",
                              }}
                            >
                              {line}
                            </Box>
                          ))}
                          {remaining > 0 ? (
                            <Box
                              component="li"
                              sx={{
                                listStyle: "none",
                                ml: -1.5,
                                pl: 0,
                                color: "var(--app-muted)",
                                fontStyle: "italic",
                              }}
                            >
                              + {remaining} more — view all
                            </Box>
                          ) : null}
                        </Box>
                      ) : null}

                      <Box sx={{ flex: 1 }} />

                      <Box
                        sx={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 0.5,
                          mt: 0.5,
                        }}
                      >
                        <Chip
                          size="small"
                          label={`${totalSteps} step${totalSteps === 1 ? "" : "s"}`}
                          sx={{
                            bgcolor: "var(--app-surface)",
                            color: "var(--app-muted)",
                            fontSize: 10,
                            height: 20,
                          }}
                        />
                        {environments.slice(0, 2).map((env) => (
                          <Chip
                            key={env}
                            size="small"
                            label={env}
                            sx={{
                              bgcolor: "var(--app-surface)",
                              color: "var(--app-muted)",
                              fontSize: 10,
                              height: 20,
                            }}
                          />
                        ))}
                        {environments.length > 2 ? (
                          <Chip
                            size="small"
                            label={`+${environments.length - 2}`}
                            sx={{
                              bgcolor: "var(--app-surface)",
                              color: "var(--app-muted)",
                              fontSize: 10,
                              height: 20,
                            }}
                          />
                        ) : null}
                      </Box>

                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Button
                          type="button"
                          variant="outlined"
                          onClick={() => setActiveBundle(bundle)}
                          sx={{
                            flex: 1,
                            textTransform: "none",
                            borderColor: "var(--app-border)",
                            color: "var(--app-fg)",
                          }}
                        >
                          View details
                        </Button>
                        <Button
                          type="button"
                          variant="contained"
                          onClick={() =>
                            void onStageBundle(
                              bundle.bundle_id,
                              bundle.title ?? bundle.bundle_id,
                            )
                          }
                          disabled={stageBusy}
                          sx={{ flex: 1, textTransform: "none" }}
                        >
                          {stageBusy ? "Staging…" : "Stage"}
                        </Button>
                      </Stack>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </Box>
        </CardContent>
      </Card>

      <BundleDetailDrawer
        bundle={activeBundle}
        open={activeBundle !== null}
        onClose={() => setActiveBundle(null)}
        busy={
          activeBundle
            ? busyKey === `bundle-${activeBundle.bundle_id}`
            : false
        }
        onStage={async (bundle) => {
          await onStageBundle(
            bundle.bundle_id,
            bundle.title ?? bundle.bundle_id,
          );
          setActiveBundle(null);
        }}
      />
    </Box>
  );
}

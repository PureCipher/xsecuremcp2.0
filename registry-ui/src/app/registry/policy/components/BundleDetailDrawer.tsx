"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
  Tooltip,
  Typography,
} from "@mui/material";
import type { PolicyBundleItem } from "@/lib/registryClient";

/**
 * Iter 14.12 — Bundle detail drawer.
 *
 * The Overview tab's bundle cards previously truncated to the first
 * three ``provider_summaries`` lines and dropped ``description``,
 * ``tags``, and the raw ``providers`` config entirely — even though
 * the registry already serializes all of those fields over the wire.
 * This drawer is the "click-through" target that surfaces the full
 * payload so a curator can see exactly what a bundle stages before
 * pressing the green button.
 *
 * Sections, top to bottom:
 *
 * 1. Header — title, risk-posture chip, recommended environments,
 *    tags, summary line.
 * 2. Long description — the multi-sentence ``description`` field
 *    (the cards show only the shorter ``summary``).
 * 3. Provider chain — every entry of ``provider_summaries`` as a
 *    numbered step. No truncation; if a bundle has 10 providers
 *    you see all 10.
 * 4. Raw JSON disclosure — collapsed by default, expands to the
 *    actual ``providers`` array. Audit-grade view for admins who
 *    need to know exactly what configuration gets staged.
 * 5. Stage button — duplicated at the bottom of the drawer so the
 *    curator can review and act in one motion.
 */
export function BundleDetailDrawer({
  bundle,
  open,
  onClose,
  onStage,
  busy,
}: {
  /** The bundle to render. ``null`` keeps the drawer closed. */
  bundle: PolicyBundleItem | null;
  open: boolean;
  onClose: () => void;
  onStage: (bundle: PolicyBundleItem) => Promise<void> | void;
  busy: boolean;
}) {
  const [showJson, setShowJson] = useState(false);

  // Reset the JSON disclosure when the drawer reopens for a new
  // bundle — otherwise the previous bundle's expanded state leaks
  // across navigation and feels broken.
  if (!bundle) {
    return (
      <Drawer anchor="right" open={open} onClose={onClose}>
        <Box sx={{ width: { xs: "100vw", md: 520 } }} />
      </Drawer>
    );
  }

  const summaries = bundle.provider_summaries ?? [];
  const providers = bundle.providers ?? [];
  const tags = bundle.tags ?? [];
  const environments = bundle.recommended_environments ?? [];

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={() => {
        setShowJson(false);
        onClose();
      }}
      slotProps={{
        paper: {
          sx: {
            width: { xs: "100vw", md: 560 },
            bgcolor: "var(--app-surface)",
          },
        },
      }}
    >
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
        }}
      >
        {/* Header */}
        <Box
          sx={{
            px: 3,
            pt: 3,
            pb: 2,
            borderBottom: "1px solid var(--app-border)",
            position: "sticky",
            top: 0,
            zIndex: 1,
            bgcolor: "var(--app-surface)",
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 1,
              mb: 1,
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Policy Bundle
              </Typography>
              <Typography
                variant="h5"
                sx={{
                  mt: 0.5,
                  fontWeight: 800,
                  color: "var(--app-fg)",
                  lineHeight: 1.2,
                  wordBreak: "break-word",
                }}
              >
                {bundle.title ?? bundle.bundle_id}
              </Typography>
              <Typography
                sx={{
                  mt: 0.5,
                  fontSize: 11,
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  color: "var(--app-muted)",
                }}
              >
                {bundle.bundle_id}
              </Typography>
            </Box>
            <Tooltip title="Close">
              <IconButton
                size="small"
                onClick={() => {
                  setShowJson(false);
                  onClose();
                }}
                aria-label="Close drawer"
              >
                <Box
                  component="svg"
                  width={18}
                  height={18}
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
          </Box>

          <Box
            sx={{
              display: "flex",
              flexWrap: "wrap",
              gap: 0.75,
              mt: 1.5,
            }}
          >
            {bundle.risk_posture ? (
              <Chip
                size="small"
                label={`risk: ${bundle.risk_posture}`}
                sx={{
                  bgcolor: "var(--app-control-active-bg)",
                  color: "var(--app-fg)",
                  fontWeight: 700,
                  fontSize: 11,
                }}
              />
            ) : null}
            {environments.map((env) => (
              <Chip
                key={env}
                size="small"
                label={env}
                sx={{
                  bgcolor: "var(--app-control-bg)",
                  color: "var(--app-muted)",
                  fontWeight: 600,
                  fontSize: 11,
                  border: "1px solid var(--app-border)",
                }}
              />
            ))}
            {tags.map((tag) => (
              <Chip
                key={tag}
                size="small"
                variant="outlined"
                label={tag}
                sx={{
                  color: "var(--app-muted)",
                  fontSize: 11,
                  borderColor: "var(--app-border)",
                }}
              />
            ))}
          </Box>

          {bundle.summary ? (
            <Typography
              sx={{
                mt: 2,
                fontSize: 13,
                color: "var(--app-fg)",
                lineHeight: 1.55,
              }}
            >
              {bundle.summary}
            </Typography>
          ) : null}
        </Box>

        {/* Scrollable body */}
        <Box
          sx={{
            flex: 1,
            overflowY: "auto",
            px: 3,
            py: 2.5,
            display: "flex",
            flexDirection: "column",
            gap: 3,
          }}
        >
          {bundle.description &&
          bundle.description !== bundle.summary ? (
            <Box>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                  mb: 1,
                }}
              >
                What this bundle does
              </Typography>
              <Typography
                sx={{
                  fontSize: 13,
                  color: "var(--app-fg)",
                  lineHeight: 1.6,
                }}
              >
                {bundle.description}
              </Typography>
            </Box>
          ) : null}

          <Box>
            <Box
              sx={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                mb: 1,
              }}
            >
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Provider chain ({summaries.length}{" "}
                {summaries.length === 1 ? "step" : "steps"})
              </Typography>
            </Box>
            {summaries.length === 0 ? (
              <Typography
                sx={{ fontSize: 12, color: "var(--app-muted)" }}
              >
                This bundle declares no provider steps — it&apos;s a
                metadata-only bundle.
              </Typography>
            ) : (
              <Box
                component="ol"
                sx={{
                  m: 0,
                  pl: 0,
                  listStyle: "none",
                  display: "grid",
                  gap: 0.75,
                  counterReset: "step",
                }}
              >
                {summaries.map((line, idx) => (
                  <Box
                    component="li"
                    key={`${bundle.bundle_id}-step-${idx}`}
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr",
                      gap: 1.25,
                      alignItems: "flex-start",
                      p: 1.25,
                      bgcolor: "var(--app-control-bg)",
                      border: "1px solid var(--app-border)",
                      borderRadius: 2,
                    }}
                  >
                    <Box
                      sx={{
                        minWidth: 24,
                        height: 24,
                        borderRadius: "50%",
                        bgcolor: "var(--app-accent)",
                        color: "var(--app-accent-contrast)",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 11,
                        fontWeight: 800,
                      }}
                    >
                      {idx + 1}
                    </Box>
                    <Typography
                      sx={{
                        fontSize: 12.5,
                        color: "var(--app-fg)",
                        lineHeight: 1.5,
                        wordBreak: "break-word",
                      }}
                    >
                      {line}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Box>

          {providers.length > 0 ? (
            <Box>
              <Button
                onClick={() => setShowJson((v) => !v)}
                size="small"
                variant="text"
                sx={{
                  textTransform: "none",
                  color: "var(--app-muted)",
                  fontSize: 12,
                  fontWeight: 700,
                  px: 0,
                  "&:hover": { bgcolor: "transparent", color: "var(--app-fg)" },
                }}
              >
                {showJson ? "▼" : "▶"} {showJson ? "Hide" : "Show"} raw provider config
                ({providers.length} {providers.length === 1 ? "entry" : "entries"})
              </Button>
              {showJson ? (
                <Box
                  component="pre"
                  sx={{
                    mt: 1,
                    p: 1.5,
                    bgcolor: "var(--app-control-bg)",
                    border: "1px solid var(--app-border)",
                    borderRadius: 2,
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: 11,
                    lineHeight: 1.55,
                    color: "var(--app-fg)",
                    maxHeight: 360,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(providers, null, 2)}
                </Box>
              ) : (
                <Typography
                  sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}
                >
                  Audit-grade view of the actual providers that get
                  staged. Click to expand.
                </Typography>
              )}
            </Box>
          ) : null}
        </Box>

        {/* Footer with Stage CTA — sticky so it stays visible while
            the body scrolls. */}
        <Box
          sx={{
            px: 3,
            py: 2,
            borderTop: "1px solid var(--app-border)",
            bgcolor: "var(--app-surface)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 2,
          }}
        >
          <Typography
            sx={{ fontSize: 11, color: "var(--app-muted)", flex: 1 }}
          >
            Staging creates a proposal — it doesn&apos;t activate the
            chain. Reviewers approve before it goes live.
          </Typography>
          <Button
            onClick={() => onStage(bundle)}
            disabled={busy}
            variant="contained"
            sx={{
              textTransform: "none",
              minWidth: 140,
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)" },
            }}
          >
            {busy ? (
              <CircularProgress size={18} sx={{ color: "inherit" }} />
            ) : (
              "Stage this bundle"
            )}
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
}

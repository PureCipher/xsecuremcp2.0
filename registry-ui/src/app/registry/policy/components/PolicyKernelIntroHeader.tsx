"use client";

import { useState } from "react";
import {
  Box,
  IconButton,
  Tooltip,
  Typography,
} from "@mui/material";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";

/**
 * Iter 14.14 — Persistent orientation header for the Policy Kernel page.
 *
 * Curators landing on ``/registry/policy`` for the first time see
 * raw analytics with no framing — they don't yet know what the page
 * decides, why it matters, or where to start. This header is a
 * one-sentence orientation that stays out of the way of operators
 * who already know the page.
 *
 * Behavior:
 *
 * - Reads ``workspace.policyKernelIntroDismissed`` from
 *   :func:`useRegistryUserPreferences`. When true, returns ``null``
 *   so the header takes zero space.
 * - Dismissal writes ``true`` back via ``updateSection``, which
 *   persists locally and syncs to the server's preference store
 *   (so the dismissal follows the user across devices).
 * - Server-side render produces nothing for this component (it's
 *   marked ``"use client"``); the first client render reads the
 *   user's stored preference and either shows or hides the header.
 *   That gives a brief render after hydration on first visit but
 *   not on subsequent visits — acceptable trade-off given the
 *   alternative is shipping the dismiss state with the SSR bundle.
 */
export function PolicyKernelIntroHeader() {
  const { prefs, updateSection } = useRegistryUserPreferences();

  // Local state mirror so dismiss feels instant — the server-sync
  // round-trip happens in the background and we don't want the
  // header lingering while we wait for it.
  const [locallyDismissed, setLocallyDismissed] = useState(false);

  if (prefs.workspace.policyKernelIntroDismissed || locallyDismissed) {
    return null;
  }

  const handleDismiss = () => {
    setLocallyDismissed(true);
    updateSection("workspace", { policyKernelIntroDismissed: true });
  };

  return (
    <Box
      role="region"
      aria-label="Policy Kernel orientation"
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 1.5,
        px: 2.25,
        py: 1.5,
        borderRadius: 2.5,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
      }}
    >
      <Box
        component="svg"
        viewBox="0 0 24 24"
        sx={{
          width: 18,
          height: 18,
          mt: 0.25,
          flexShrink: 0,
          color: "var(--app-accent)",
        }}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <circle cx={12} cy={12} r={10} />
        <line x1={12} y1={16} x2={12} y2={12} />
        <line x1={12} y1={8} x2={12.01} y2={8} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          sx={{
            fontSize: 13,
            fontWeight: 700,
            color: "var(--app-fg)",
            lineHeight: 1.45,
          }}
        >
          The Policy Kernel decides which clients can call which tools — and
          proves the decision afterward.
        </Typography>
        <Typography
          sx={{
            mt: 0.5,
            fontSize: 12,
            color: "var(--app-muted)",
            lineHeight: 1.55,
          }}
        >
          Use{" "}
          <Box component="strong" sx={{ color: "var(--app-fg)" }}>
            Catalog
          </Box>{" "}
          to install proven policy bundles,{" "}
          <Box component="strong" sx={{ color: "var(--app-fg)" }}>
            Proposals
          </Box>{" "}
          to review staged changes before they go live, and{" "}
          <Box component="strong" sx={{ color: "var(--app-fg)" }}>
            Versions
          </Box>{" "}
          to roll back if a change misbehaves.{" "}
          <Box
            component="a"
            href="https://docs.purecipher.com/policy-kernel"
            target="_blank"
            rel="noreferrer"
            sx={{
              color: "var(--app-accent)",
              textDecoration: "none",
              fontWeight: 600,
              "&:hover": { textDecoration: "underline" },
            }}
          >
            Why does this matter?
          </Box>
        </Typography>
      </Box>
      <Tooltip title="Dismiss — won't show again">
        <IconButton
          size="small"
          onClick={handleDismiss}
          aria-label="Dismiss Policy Kernel orientation"
          sx={{ flexShrink: 0, mt: -0.25, color: "var(--app-muted)" }}
        >
          <Box
            component="svg"
            width={16}
            height={16}
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
  );
}

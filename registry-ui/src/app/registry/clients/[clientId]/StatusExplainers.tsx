"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Chip,
  Popover,
  Typography,
} from "@mui/material";

/**
 * Iter 14.36 — Activity / admin status explainers.
 *
 * Symmetric to Iter 14.32 on the listing side. Where that wrapper
 * makes a certification tier explain itself, this one makes the
 * lifecycle (live/recent/idle/dormant/never) and admin
 * (active/suspended) chips explain themselves.
 *
 * Two exported components:
 *
 *   - ActivityStatusExplainer — wraps the lifecycle chip. Click to
 *     see a popover with the exact thresholds the backend uses to
 *     compute the label, plus what each label implies for the
 *     operator.
 *
 *   - AdminStatusExplainer — wraps the active/suspended admin
 *     chip. Click to see what each state means for traffic and
 *     governance.
 *
 * The thresholds shown in the activity popover mirror the ones in
 * `PureCipherRegistry._summarize_client_activity`:
 *
 *   live    ≤ 60 s   (one minute since last seen)
 *   recent  ≤ 15 min
 *   idle    ≤ 24 h
 *   dormant > 24 h
 *   never   no last_seen_at recorded
 *
 * If a future iter changes those bucket boundaries, this file is
 * the second place to update — the backend constant is the source
 * of truth.
 */

// ── Shared UI ─────────────────────────────────────────────────

type ChipColor = "success" | "info" | "warning" | "default" | "error";

function ChipColorSx(color: ChipColor) {
  if (color === "success") {
    return {
      bgcolor: "rgba(34, 197, 94, 0.10)",
      color: "#15803d",
      borderColor: "rgba(74, 222, 128, 0.4)",
    };
  }
  if (color === "info") {
    return {
      bgcolor: "rgba(59, 130, 246, 0.10)",
      color: "#1e40af",
      borderColor: "rgba(96, 165, 250, 0.4)",
    };
  }
  if (color === "warning") {
    return {
      bgcolor: "rgba(245, 158, 11, 0.12)",
      color: "#92400e",
      borderColor: "rgba(251, 191, 36, 0.4)",
    };
  }
  if (color === "error") {
    return {
      bgcolor: "rgba(244, 63, 94, 0.10)",
      color: "#b91c1c",
      borderColor: "rgba(248, 113, 113, 0.4)",
    };
  }
  return {
    bgcolor: "var(--app-control-bg)",
    color: "var(--app-muted)",
    borderColor: "var(--app-border)",
  };
}

function ExplainerShell({
  buttonLabel,
  buttonColor,
  popoverTitle,
  highlight,
  highlightLabel,
  children,
}: {
  buttonLabel: string;
  buttonColor: ChipColor;
  popoverTitle: string;
  highlight: ChipColor;
  highlightLabel: string;
  children: React.ReactNode;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const open = (e: React.MouseEvent<HTMLElement>) => setAnchor(e.currentTarget);
  const close = () => setAnchor(null);

  return (
    <>
      <Box
        component="button"
        type="button"
        onClick={open}
        aria-label={`${popoverTitle}: ${buttonLabel}. Click for details.`}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.5,
          background: "none",
          border: "none",
          p: 0,
          cursor: "pointer",
          borderRadius: 1.5,
          "&:hover": { opacity: 0.85 },
          "&:focus-visible": {
            outline: "2px solid var(--app-accent)",
            outlineOffset: 2,
          },
        }}
      >
        <Chip
          size="small"
          label={buttonLabel}
          sx={{
            fontWeight: 700,
            fontSize: 11,
            height: 22,
            border: "1px solid",
            ...ChipColorSx(buttonColor),
          }}
        />
        <Box
          component="span"
          aria-hidden
          sx={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 16,
            height: 16,
            borderRadius: "50%",
            bgcolor: "var(--app-control-bg)",
            border: "1px solid var(--app-border)",
            color: "var(--app-muted)",
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          ?
        </Box>
      </Box>

      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{
          paper: {
            sx: {
              maxWidth: 380,
              border: "1px solid var(--app-border)",
              boxShadow: "0 14px 38px rgba(15, 23, 42, 0.12)",
              borderRadius: 3,
            },
          },
        }}
      >
        <Box sx={{ p: 2.5 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "baseline",
              gap: 1,
              mb: 1,
            }}
          >
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              {popoverTitle}
            </Typography>
            <Chip
              size="small"
              label={highlightLabel}
              sx={{
                fontWeight: 700,
                fontSize: 11,
                height: 22,
                border: "1px solid",
                ...ChipColorSx(highlight),
              }}
            />
          </Box>

          {children}

          <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 1.5 }}>
            <Button
              size="small"
              variant="text"
              onClick={close}
              sx={{
                textTransform: "none",
                fontSize: 12,
                color: "var(--app-muted)",
              }}
            >
              Close
            </Button>
          </Box>
        </Box>
      </Popover>
    </>
  );
}

// ── Activity status explainer ────────────────────────────────

type ActivityStatusKey = "live" | "recent" | "idle" | "dormant" | "never";

const ACTIVITY_TABLE: Record<
  ActivityStatusKey,
  {
    label: string;
    color: ChipColor;
    threshold: string;
    description: string;
  }
> = {
  live: {
    label: "Live",
    color: "success",
    threshold: "≤ 60 seconds since last call",
    description:
      "The client made an authenticated call within the last minute. It is actively talking to the registry right now.",
  },
  recent: {
    label: "Recent",
    color: "info",
    threshold: "≤ 15 minutes since last call",
    description:
      "Recently active but not currently calling. Treat as healthy — the client is online and connected.",
  },
  idle: {
    label: "Idle",
    color: "warning",
    threshold: "≤ 24 hours since last call",
    description:
      "Quieter than usual. May be a low-traffic batch client, may be asleep. Worth a quick check if you expect continuous calls.",
  },
  dormant: {
    label: "Dormant",
    color: "default",
    threshold: "> 24 hours since last call",
    description:
      "No traffic in the last day. Either the workload finished, the client is decommissioned, or its credentials silently broke. Consider revoking unused tokens here.",
  },
  never: {
    label: "Never seen",
    color: "default",
    threshold: "no authenticated call recorded",
    description:
      "The client has been onboarded but has never made an authenticated call. Common right after issuing the first token — it should transition once the operator wires it in.",
  },
};

function activityKey(value: string | undefined): ActivityStatusKey {
  if (value === "live" || value === "recent" || value === "idle" ||
      value === "dormant" || value === "never") {
    return value;
  }
  return "never";
}

export function ActivityStatusExplainer({ status }: { status: string | undefined }) {
  const key = activityKey(status);
  const info = ACTIVITY_TABLE[key];

  return (
    <ExplainerShell
      buttonLabel={info.label}
      buttonColor={info.color}
      popoverTitle="Activity status"
      highlight={info.color}
      highlightLabel={info.label}
    >
      <Typography
        sx={{
          fontSize: 13,
          color: "var(--app-fg)",
          lineHeight: 1.55,
          mb: 1.5,
        }}
      >
        <strong>{info.threshold}.</strong> {info.description}
      </Typography>

      <Typography
        sx={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
          mb: 0.75,
        }}
      >
        All thresholds
      </Typography>
      <Box
        component="dl"
        sx={{
          m: 0,
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          rowGap: 0.5,
          columnGap: 1,
          fontSize: 12,
          color: "var(--app-muted)",
          lineHeight: 1.5,
        }}
      >
        {(Object.keys(ACTIVITY_TABLE) as ActivityStatusKey[]).map((k) => {
          const row = ACTIVITY_TABLE[k];
          const isCurrent = k === key;
          return (
            <Box key={k} sx={{ display: "contents" }}>
              <Typography
                component="dt"
                sx={{
                  fontWeight: isCurrent ? 800 : 700,
                  color: isCurrent ? "var(--app-fg)" : "var(--app-muted)",
                  fontSize: 12,
                }}
              >
                {row.label}
              </Typography>
              <Typography
                component="dd"
                sx={{
                  m: 0,
                  fontSize: 12,
                  color: isCurrent ? "var(--app-fg)" : "var(--app-muted)",
                }}
              >
                {row.threshold}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <Typography
        sx={{
          mt: 1.5,
          fontSize: 11,
          color: "var(--app-muted)",
          fontStyle: "italic",
          lineHeight: 1.5,
        }}
      >
        Computed from the provenance ledger (which records every authenticated
        call) and from the token table&apos;s last_used_at fallback. Refreshes
        every 10 seconds while the activity panel is mounted.
      </Typography>
    </ExplainerShell>
  );
}

// ── Admin status explainer ───────────────────────────────────

type AdminStatusKey = "active" | "suspended";

const ADMIN_TABLE: Record<
  AdminStatusKey,
  {
    label: string;
    color: ChipColor;
    description: string;
    consequences: string[];
  }
> = {
  active: {
    label: "Active",
    color: "success",
    description:
      "The client is in good standing. Tokens authenticate normally and calls flow through every governance plane (policy, contract, consent, ledger, reflexive).",
    consequences: [
      "Issued tokens authenticate against the registry.",
      "Calls are routed and recorded under the client's slug.",
      "Reflexive analyzer evaluates this client's traffic for drift.",
    ],
  },
  suspended: {
    label: "Suspended",
    color: "warning",
    description:
      "An admin marked the client suspended. The registry rejects every authenticated call from this client with HTTP 403 until it is reinstated.",
    consequences: [
      "All token bearer requests fail with 403.",
      "Existing contracts and consent grants persist but are unreachable.",
      "Audit history remains intact — suspension does not delete records.",
      "Use Unsuspend to restore traffic without re-issuing tokens.",
    ],
  },
};

function adminKey(value: string | undefined): AdminStatusKey {
  return value === "suspended" ? "suspended" : "active";
}

export function AdminStatusExplainer({ status }: { status: string | undefined }) {
  const key = adminKey(status);
  const info = ADMIN_TABLE[key];

  return (
    <ExplainerShell
      buttonLabel={info.label}
      buttonColor={info.color}
      popoverTitle="Admin status"
      highlight={info.color}
      highlightLabel={info.label}
    >
      <Typography
        sx={{
          fontSize: 13,
          color: "var(--app-fg)",
          lineHeight: 1.55,
          mb: 1.5,
        }}
      >
        {info.description}
      </Typography>

      <Typography
        sx={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
          mb: 0.75,
        }}
      >
        What this means in practice
      </Typography>
      <Box
        component="ul"
        sx={{
          m: 0,
          pl: 2.5,
          display: "grid",
          gap: 0.5,
          fontSize: 12.5,
          color: "var(--app-muted)",
          lineHeight: 1.5,
        }}
      >
        {info.consequences.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </Box>
    </ExplainerShell>
  );
}

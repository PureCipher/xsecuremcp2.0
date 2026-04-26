"use client";

import { Chip } from "@mui/material";

const STATUS_COLORS: Record<string, { bgcolor: string; color: string }> = {
  // General
  ok: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  healthy: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  active: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },

  // Compliance
  compliant: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  elevated_risk: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },
  non_compliant: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },
  unknown: { bgcolor: "rgba(100, 116, 139, 0.12)", color: "var(--app-muted)" },

  // Threat levels
  none: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  low: { bgcolor: "rgba(14, 165, 233, 0.12)", color: "#0369a1" },
  medium: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },
  high: { bgcolor: "rgba(249, 115, 22, 0.12)", color: "#c2410c" },
  critical: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },

  // Verdicts
  proceed: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  throttle: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },
  require_confirmation: { bgcolor: "rgba(249, 115, 22, 0.12)", color: "#c2410c" },
  halt: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },

  // Contract statuses
  proposed: { bgcolor: "rgba(14, 165, 233, 0.12)", color: "#0369a1" },
  negotiating: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },
  accepted: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  rejected: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },
  expired: { bgcolor: "rgba(100, 116, 139, 0.12)", color: "var(--app-muted)" },
  revoked: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },
  pending: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },

  // Consent
  granted: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  denied: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },
  conditional: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },

  // Default
  default: { bgcolor: "rgba(100, 116, 139, 0.12)", color: "var(--app-muted)" },
};

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const normalized = status.toLowerCase().replace(/[\s-]/g, "_");
  const colors = STATUS_COLORS[normalized] || STATUS_COLORS.default;
  return (
    <Chip
      className={className}
      size="small"
      label={status.replace(/_/g, " ")}
      sx={{
        borderRadius: 2,
        height: 24,
        bgcolor: colors.bgcolor,
        color: colors.color,
        fontSize: 11,
        fontWeight: 700,
        textTransform: "none",
        letterSpacing: "0.01em",
      }}
    />
  );
}

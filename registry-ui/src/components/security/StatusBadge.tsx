"use client";

import { Chip } from "@mui/material";

const STATUS_COLORS: Record<string, { bgcolor: string; color: string }> = {
  // General
  ok: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  healthy: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  active: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },

  // Compliance
  compliant: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  elevated_risk: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },
  non_compliant: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },
  unknown: { bgcolor: "rgba(113, 113, 122, 0.18)", color: "rgb(212, 212, 216)" },

  // Threat levels
  none: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  low: { bgcolor: "rgba(14, 165, 233, 0.18)", color: "rgb(186, 230, 253)" },
  medium: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },
  high: { bgcolor: "rgba(249, 115, 22, 0.18)", color: "rgb(254, 215, 170)" },
  critical: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },

  // Verdicts
  proceed: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  throttle: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },
  require_confirmation: { bgcolor: "rgba(249, 115, 22, 0.18)", color: "rgb(254, 215, 170)" },
  halt: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },

  // Contract statuses
  proposed: { bgcolor: "rgba(14, 165, 233, 0.18)", color: "rgb(186, 230, 253)" },
  negotiating: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },
  accepted: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  rejected: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },
  expired: { bgcolor: "rgba(113, 113, 122, 0.18)", color: "rgb(212, 212, 216)" },
  revoked: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },
  pending: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },

  // Consent
  granted: { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" },
  denied: { bgcolor: "rgba(239, 68, 68, 0.18)", color: "rgb(254, 202, 202)" },
  conditional: { bgcolor: "rgba(245, 158, 11, 0.18)", color: "rgb(253, 230, 138)" },

  // Default
  default: { bgcolor: "rgba(113, 113, 122, 0.18)", color: "rgb(212, 212, 216)" },
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
        borderRadius: 999,
        height: 22,
        bgcolor: colors.bgcolor,
        color: colors.color,
        fontSize: 10,
        fontWeight: 800,
        textTransform: "uppercase",
        letterSpacing: "0.12em",
      }}
    />
  );
}

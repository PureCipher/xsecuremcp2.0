type Props = {
  level?: string;
  size?: "sm" | "md";
};

type Info = {
  raw: string | null;
  label: string;
  bgcolor: string;
  color: string;
  borderColor: string;
};

import { Chip } from "@mui/material";

function info(level?: string): Info {
  const raw = level?.trim() ? level.trim() : null;
  const upper = raw?.toUpperCase?.() ?? "";

  if (!raw || upper === "UNRATED" || upper === "NONE" || upper === "UNKNOWN") {
    return {
      raw,
      label: "Unrated",
      bgcolor: "rgba(100, 116, 139, 0.12)",
      color: "var(--app-muted)",
      borderColor: "var(--app-control-border)",
    };
  }

  if (upper.includes("CERTIFIED") || upper.includes("VERIFIED") || upper.includes("TRUSTED")) {
    return {
      raw,
      label: raw,
      bgcolor: "var(--app-control-active-bg)",
      color: "var(--app-fg)",
      borderColor: "var(--app-accent)",
    };
  }

  if (upper.includes("ATTEST") || upper.includes("SIGNED")) {
    return {
      raw,
      label: raw,
      bgcolor: "rgba(14, 165, 233, 0.12)",
      color: "#0369a1",
      borderColor: "rgba(14, 165, 233, 0.22)",
    };
  }

  return {
    raw,
    label: raw,
    bgcolor: "var(--app-control-bg)",
    color: "var(--app-muted)",
    borderColor: "var(--app-surface-ring)",
  };
}

export function CertificationBadge({ level, size = "sm" }: Props) {
  const badge = info(level);
  const height = size === "md" ? 24 : 22;

  return (
    <Chip
      title={badge.raw ?? "Unrated"}
      size="small"
      label={badge.label}
      sx={{
        borderRadius: 2,
        height,
        bgcolor: badge.bgcolor,
        color: badge.color,
        border: "1px solid",
        borderColor: badge.borderColor,
        fontSize: 11,
        fontWeight: 700,
        textTransform: "none",
        letterSpacing: "0.01em",
        "& .MuiChip-label": {
          px: size === "md" ? 1.25 : 1,
        },
      }}
    />
  );
}


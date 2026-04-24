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
      bgcolor: "rgba(113, 113, 122, 0.18)",
      color: "rgb(212, 212, 216)",
      borderColor: "rgba(212, 212, 216, 0.24)",
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
      bgcolor: "rgba(14, 165, 233, 0.18)",
      color: "rgb(186, 230, 253)",
      borderColor: "rgba(186, 230, 253, 0.24)",
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
        borderRadius: 999,
        height,
        bgcolor: badge.bgcolor,
        color: badge.color,
        border: "1px solid",
        borderColor: badge.borderColor,
        fontSize: 10,
        fontWeight: 800,
        textTransform: "uppercase",
        letterSpacing: "0.16em",
        "& .MuiChip-label": {
          px: size === "md" ? 1.25 : 1,
        },
      }}
    />
  );
}


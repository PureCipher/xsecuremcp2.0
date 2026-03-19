type Props = {
  level?: string;
  size?: "sm" | "md";
};

type Info = {
  raw: string | null;
  label: string;
  className: string;
};

function info(level?: string): Info {
  const raw = level?.trim() ? level.trim() : null;
  const upper = raw?.toUpperCase?.() ?? "";

  if (!raw || upper === "UNRATED" || upper === "NONE" || upper === "UNKNOWN") {
    return {
      raw,
      label: "Unrated",
      className: "bg-zinc-500/10 text-zinc-200 ring-1 ring-zinc-400/20",
    };
  }

  if (upper.includes("CERTIFIED") || upper.includes("VERIFIED") || upper.includes("TRUSTED")) {
    return {
      raw,
      label: raw,
      className: "bg-[--app-control-active-bg] text-[--app-fg] ring-1 ring-[--app-accent]",
    };
  }

  if (upper.includes("ATTEST") || upper.includes("SIGNED")) {
    return {
      raw,
      label: raw,
      className: "bg-sky-500/10 text-sky-100 ring-1 ring-sky-400/20",
    };
  }

  return {
    raw,
    label: raw,
    className: "bg-[--app-control-bg] text-[--app-muted] ring-1 ring-[--app-surface-ring]",
  };
}

export function CertificationBadge({ level, size = "sm" }: Props) {
  const badge = info(level);
  const textSize = size === "md" ? "text-[10px]" : "text-[10px]";
  const padding = size === "md" ? "px-3 py-1" : "px-2 py-0.5";

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold uppercase tracking-[0.16em] ${textSize} ${padding} ${badge.className}`}
      title={badge.raw ?? "Unrated"}
    >
      {badge.label}
    </span>
  );
}


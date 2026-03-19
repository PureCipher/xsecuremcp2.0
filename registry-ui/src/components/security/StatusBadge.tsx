"use client";

const STATUS_COLORS: Record<string, string> = {
  // General
  ok: "bg-[--app-control-active-bg] text-[--app-fg]",
  healthy: "bg-[--app-control-active-bg] text-[--app-fg]",
  active: "bg-[--app-control-active-bg] text-[--app-fg]",

  // Compliance
  compliant: "bg-[--app-control-active-bg] text-[--app-fg]",
  elevated_risk: "bg-amber-500/20 text-amber-300",
  non_compliant: "bg-red-500/20 text-red-300",
  unknown: "bg-zinc-500/20 text-zinc-300",

  // Threat levels
  none: "bg-[--app-control-active-bg] text-[--app-fg]",
  low: "bg-sky-500/20 text-sky-300",
  medium: "bg-amber-500/20 text-amber-300",
  high: "bg-orange-500/20 text-orange-300",
  critical: "bg-red-500/20 text-red-300",

  // Verdicts
  proceed: "bg-[--app-control-active-bg] text-[--app-fg]",
  throttle: "bg-amber-500/20 text-amber-300",
  require_confirmation: "bg-orange-500/20 text-orange-300",
  halt: "bg-red-500/20 text-red-300",

  // Contract statuses
  proposed: "bg-sky-500/20 text-sky-300",
  negotiating: "bg-amber-500/20 text-amber-300",
  accepted: "bg-[--app-control-active-bg] text-[--app-fg]",
  rejected: "bg-red-500/20 text-red-300",
  expired: "bg-zinc-500/20 text-zinc-300",
  revoked: "bg-red-500/20 text-red-300",
  pending: "bg-amber-500/20 text-amber-300",

  // Consent
  granted: "bg-[--app-control-active-bg] text-[--app-fg]",
  denied: "bg-red-500/20 text-red-300",
  conditional: "bg-amber-500/20 text-amber-300",

  // Default
  default: "bg-zinc-500/20 text-zinc-300",
};

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const normalized = status.toLowerCase().replace(/[\s-]/g, "_");
  const colors = STATUS_COLORS[normalized] || STATUS_COLORS.default;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${colors} ${className}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

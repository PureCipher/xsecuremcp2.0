"use client";

export function MetricCard({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: string | number;
  detail?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
        {label}
      </p>
      <p className={`mt-2 text-lg font-bold ${accent ? "text-[--app-accent]" : "text-[--app-fg]"}`}>
        {value}
      </p>
      {detail ? (
        <p className="mt-1 text-[11px] text-[--app-muted]">{detail}</p>
      ) : null}
    </div>
  );
}

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
    <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
        {label}
      </p>
      <p className={`mt-2 text-lg font-bold ${accent ? "text-emerald-400" : "text-emerald-50"}`}>
        {value}
      </p>
      {detail ? (
        <p className="mt-1 text-[11px] text-emerald-200/80">{detail}</p>
      ) : null}
    </div>
  );
}

"use client";

export function KeyValuePanel({
  title,
  entries,
}: {
  title?: string;
  entries: { label: string; value: React.ReactNode }[];
}) {
  return (
    <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
      {title ? (
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
          {title}
        </p>
      ) : null}
      <dl className="space-y-2">
        {entries.map((e) => (
          <div key={e.label} className="flex items-baseline justify-between gap-3">
            <dt className="text-[11px] text-emerald-300/80">{e.label}</dt>
            <dd className="text-right text-[12px] font-medium text-emerald-50">{e.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

"use client";

export function KeyValuePanel({
  title,
  entries,
}: {
  title?: string;
  entries: { label: string; value: React.ReactNode }[];
}) {
  return (
    <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
      {title ? (
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          {title}
        </p>
      ) : null}
      <dl className="space-y-2">
        {entries.map((e) => (
          <div key={e.label} className="flex items-baseline justify-between gap-3">
            <dt className="text-[11px] text-[--app-muted]">{e.label}</dt>
            <dd className="text-right text-[12px] font-medium text-[--app-fg]">{e.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

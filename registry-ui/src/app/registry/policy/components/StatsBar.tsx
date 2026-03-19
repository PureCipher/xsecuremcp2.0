"use client";

type StatsBarProps = {
  stats: Array<{ label: string; value: string }>;
};

export function StatsBar({ stats }: StatsBarProps) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {stats.map((item) => (
        <div
          key={item.label}
          className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]"
        >
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            {item.label}
          </p>
          <p className="mt-2 text-2xl font-semibold text-[--app-fg]">
            {item.value}
          </p>
        </div>
      ))}
    </section>
  );
}

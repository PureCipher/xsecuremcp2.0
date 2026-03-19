export function EmptyState({
  title,
  message,
}: {
  title: string;
  message?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-[--app-border] bg-[--app-control-bg] py-12 ring-1 ring-[--app-surface-ring]">
      <div className="mb-2 text-2xl text-[--app-accent]/60">∅</div>
      <p className="text-[12px] font-semibold text-[--app-fg]">{title}</p>
      {message ? (
        <p className="mt-1 text-[11px] text-[--app-muted]">{message}</p>
      ) : null}
    </div>
  );
}

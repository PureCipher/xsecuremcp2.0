export function EmptyState({
  title,
  message,
}: {
  title: string;
  message?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl bg-emerald-900/20 py-12 ring-1 ring-emerald-700/30">
      <div className="mb-2 text-2xl text-emerald-500/50">∅</div>
      <p className="text-[12px] font-semibold text-emerald-100">{title}</p>
      {message ? (
        <p className="mt-1 text-[11px] text-emerald-200/70">{message}</p>
      ) : null}
    </div>
  );
}

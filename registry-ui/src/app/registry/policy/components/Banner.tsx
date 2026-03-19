"use client";

type BannerProps = {
  tone: "success" | "error";
  message: string;
  onDismiss?: () => void;
};

export function Banner({ tone, message, onDismiss }: BannerProps) {
  const colors =
    tone === "success"
      ? "bg-[--app-surface] text-[--app-fg] ring-[--app-surface-ring]"
      : "bg-rose-950/40 text-rose-50 ring-rose-700/60";

  return (
    <section className={`flex items-center justify-between rounded-3xl p-4 ring-1 ${colors}`}>
      <p className="text-xs font-medium">{message}</p>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-4 text-xs font-medium opacity-70 transition hover:opacity-100"
          aria-label="Dismiss"
        >
          Dismiss
        </button>
      ) : null}
    </section>
  );
}

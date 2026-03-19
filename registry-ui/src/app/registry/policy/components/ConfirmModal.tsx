"use client";

import { useEffect, useRef, type ReactNode } from "react";

type ConfirmModalProps = {
  isOpen: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDangerous?: boolean;
  isLoading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  children?: ReactNode;
};

export function ConfirmModal({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isDangerous = false,
  isLoading = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !isLoading) {
        onCancel();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    confirmRef.current?.focus();

    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isLoading, onCancel]);

  if (!isOpen) return null;

  const confirmClasses = isDangerous
    ? "bg-rose-500 text-white hover:bg-rose-400 disabled:opacity-60"
    : "bg-[--app-accent] text-[--app-accent-contrast] hover:opacity-90 disabled:opacity-60";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget && !isLoading) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="mx-4 w-full max-w-md rounded-3xl border border-[--app-border] bg-[--app-chrome-bg] p-6 ring-1 ring-[--app-surface-ring] shadow-2xl">
        <h3 className="text-lg font-semibold text-[--app-fg]">{title}</h3>

        {description ? (
          <p className="mt-2 text-xs text-[--app-muted]">{description}</p>
        ) : null}

        {children ? <div className="mt-4">{children}</div> : null}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="rounded-full border border-[--app-border] px-4 py-2 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-60"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={() => void onConfirm()}
            disabled={isLoading}
            className={`rounded-full px-4 py-2 text-[11px] font-semibold transition ${confirmClasses}`}
          >
            {isLoading ? "Working\u2026" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

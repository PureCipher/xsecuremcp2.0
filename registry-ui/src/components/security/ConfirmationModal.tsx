"use client";

import { useEffect, useRef } from "react";

export function ConfirmationModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-3xl bg-emerald-950 p-6 ring-1 ring-emerald-700/60">
        <h3 className="text-sm font-semibold text-emerald-50">{title}</h3>
        <p className="mt-2 text-[12px] text-emerald-200/80">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-emerald-700/60 px-4 py-1.5 text-[11px] font-medium text-emerald-200 transition hover:bg-emerald-900/50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-full px-4 py-1.5 text-[11px] font-semibold transition ${
              danger
                ? "bg-red-600/80 text-red-50 hover:bg-red-600"
                : "bg-emerald-600/80 text-emerald-50 hover:bg-emerald-600"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

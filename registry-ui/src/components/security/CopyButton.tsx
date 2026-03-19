"use client";

import { useEffect, useState } from "react";

async function writeToClipboard(text: string): Promise<boolean> {
  if (typeof navigator === "undefined") return false;

  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers / blocked clipboard permission
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.left = "-1000px";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

export function CopyButton({
  text,
  label = "Copy",
  className = "",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (status === "idle") return;
    const t = window.setTimeout(() => setStatus("idle"), 1200);
    return () => window.clearTimeout(t);
  }, [status]);

  return (
    <button
      type="button"
      onClick={async () => {
        const ok = await writeToClipboard(text);
        setStatus(ok ? "copied" : "failed");
      }}
      className={`rounded-full border border-[--app-border] bg-[--app-control-bg] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] ${className}`}
      aria-label={label}
    >
      {status === "copied" ? "Copied" : status === "failed" ? "Failed" : label}
    </button>
  );
}


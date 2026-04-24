"use client";

import { useEffect, useState } from "react";
import { Button } from "@mui/material";

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

  const currentLabel = status === "copied" ? "Copied" : status === "failed" ? "Failed" : label;

  return (
    <Button
      type="button"
      onClick={async () => {
        const ok = await writeToClipboard(text);
        setStatus(ok ? "copied" : "failed");
      }}
      className={className}
      aria-label={label}
      variant="outlined"
      size="small"
      sx={{
        borderRadius: 999,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        color: "var(--app-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.16em",
        fontWeight: 800,
        fontSize: 10,
        px: 1.5,
        py: 0.4,
        minWidth: 0,
        "&:hover": {
          bgcolor: "var(--app-hover-bg)",
          borderColor: "var(--app-border)",
          color: "var(--app-fg)",
        },
      }}
    >
      {currentLabel}
    </Button>
  );
}


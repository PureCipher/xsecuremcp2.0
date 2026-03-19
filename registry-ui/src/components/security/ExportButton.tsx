"use client";

import { useCallback } from "react";

export function ExportButton({
  data,
  filename = "export",
  format = "json",
  label,
}: {
  data: unknown;
  filename?: string;
  format?: "json" | "csv";
  label?: string;
}) {
  const handleExport = useCallback(() => {
    let content: string;
    let mimeType: string;
    let ext: string;

    if (format === "csv" && Array.isArray(data) && data.length > 0) {
      const headers = Object.keys(data[0] as Record<string, unknown>);
      const rows = data.map((row) =>
        headers
          .map((h) => {
            const val = (row as Record<string, unknown>)[h];
            const str = val == null ? "" : String(val);
            return str.includes(",") || str.includes('"')
              ? `"${str.replace(/"/g, '""')}"`
              : str;
          })
          .join(","),
      );
      content = [headers.join(","), ...rows].join("\n");
      mimeType = "text/csv";
      ext = "csv";
    } else {
      content = JSON.stringify(data, null, 2);
      mimeType = "application/json";
      ext = "json";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [data, filename, format]);

  return (
    <button
      type="button"
      onClick={handleExport}
      className="rounded-full border border-[--app-border] px-3 py-1 text-[10px] font-medium text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
    >
      {label ?? `Export ${format.toUpperCase()}`}
    </button>
  );
}

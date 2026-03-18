"use client";

import { useState, useMemo } from "react";

export type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
};

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  onRowClick,
  pageSize = 10,
  emptyMessage = "No data available",
}: {
  data: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  pageSize?: number;
  emptyMessage?: string;
}) {
  const [page, setPage] = useState(0);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    return [...data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-3xl bg-emerald-900/20 py-10 ring-1 ring-emerald-700/30">
        <p className="text-[11px] text-emerald-200/70">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl ring-1 ring-emerald-700/60">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px]">
          <thead>
            <tr className="border-b border-emerald-700/50 bg-emerald-900/60">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2.5 font-semibold uppercase tracking-wider text-emerald-300 ${
                    col.sortable !== false ? "cursor-pointer select-none hover:text-emerald-200" : ""
                  }`}
                  onClick={col.sortable !== false ? () => handleSort(col.key) : undefined}
                >
                  <span className="flex items-center gap-1">
                    {col.header}
                    {sortKey === col.key ? (
                      <span className="text-emerald-400">{sortDir === "asc" ? "↑" : "↓"}</span>
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, i) => (
              <tr
                key={i}
                className={`border-b border-emerald-800/30 bg-emerald-900/20 transition ${
                  onRowClick ? "cursor-pointer hover:bg-emerald-800/30" : ""
                }`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2 text-emerald-100">
                    {col.render ? col.render(row) : String(row[col.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 ? (
        <div className="flex items-center justify-between border-t border-emerald-700/50 bg-emerald-900/40 px-3 py-2">
          <p className="text-[10px] text-emerald-300/70">
            {sorted.length} row{sorted.length !== 1 ? "s" : ""} · Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="rounded-full px-2 py-0.5 text-[10px] font-medium text-emerald-200 transition hover:bg-emerald-800/50 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              type="button"
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="rounded-full px-2 py-0.5 text-[10px] font-medium text-emerald-200 transition hover:bg-emerald-800/50 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

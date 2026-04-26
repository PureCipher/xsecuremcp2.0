"use client";

import { useState, useMemo } from "react";

import {
  Box,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Typography,
} from "@mui/material";

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
  const [rowsPerPage, setRowsPerPage] = useState(pageSize);
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

  const paged = sorted.slice(page * rowsPerPage, (page + 1) * rowsPerPage);

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
      <Card variant="outlined">
        <CardContent sx={{ py: 6 }}>
          <Typography sx={{ textAlign: "center", fontSize: 12, color: "var(--app-muted)" }}>{emptyMessage}</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="outlined" sx={{ overflow: "hidden" }}>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: "var(--app-control-bg)" }}>
              {columns.map((col) => {
                const sortable = col.sortable !== false;
                const active = sortKey === col.key;
                return (
                  <TableCell
                    key={col.key}
                    onClick={sortable ? () => handleSort(col.key) : undefined}
                    sx={{
                      color: "var(--app-muted)",
                      fontSize: 12,
                      fontWeight: 700,
                      textTransform: "none",
                      letterSpacing: "0.01em",
                      cursor: sortable ? "pointer" : "default",
                      userSelect: sortable ? "none" : "auto",
                      borderBottom: "1px solid var(--app-border)",
                    }}
                  >
                    {sortable ? (
                      <TableSortLabel
                        active={active}
                        direction={active ? sortDir : "asc"}
                        sx={{
                          color: "inherit !important",
                          "& .MuiTableSortLabel-icon": { color: "var(--app-accent) !important" },
                        }}
                      >
                        {col.header}
                      </TableSortLabel>
                    ) : (
                      col.header
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          </TableHead>
          <TableBody>
            {paged.map((row, i) => (
              <TableRow
                key={i}
                hover={!!onRowClick}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                sx={{
                  cursor: onRowClick ? "pointer" : "default",
                  "& td": { borderBottom: "1px solid var(--app-border)", color: "var(--app-muted)", fontSize: 13 },
                  "&:last-child td": { borderBottom: 0 },
                }}
              >
                {columns.map((col) => (
                  <TableCell key={col.key}>
                    {col.render ? col.render(row) : String(row[col.key] ?? "—")}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ borderTop: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
        <TablePagination
          component="div"
          count={sorted.length}
          page={page}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            const next = Number(e.target.value);
            setRowsPerPage(next);
            setPage(0);
          }}
          rowsPerPageOptions={[5, 10, 25, 50]}
          labelRowsPerPage="Rows"
          sx={{
            color: "var(--app-muted)",
            "& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows": { fontSize: 11 },
            "& .MuiSelect-select": { fontSize: 11 },
          }}
        />
      </Box>
    </Card>
  );
}

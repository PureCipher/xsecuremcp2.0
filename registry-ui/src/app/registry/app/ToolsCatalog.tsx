"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { RegistryToolListing } from "@/lib/registryClient";

type SortMode = "certification_desc" | "name_asc";

type Props = {
  tools: RegistryToolListing[];
};

type CertificationInfo = {
  raw: string | null;
  label: string;
  tier: number;
  className: string;
};

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replaceAll(/\p{Diacritic}+/gu, "")
    .trim();
}

function certificationInfo(level?: string): CertificationInfo {
  const raw = level?.trim() ? level.trim() : null;
  const upper = raw?.toUpperCase?.() ?? "";

  if (!raw || upper === "UNRATED" || upper === "NONE" || upper === "UNKNOWN") {
    return {
      raw,
      label: "Unrated",
      tier: 0,
      className: "bg-zinc-500/10 text-zinc-200 ring-1 ring-zinc-400/20",
    };
  }

  // We don't have a fixed enum here; prefer a stable ordering heuristic that still
  // sorts "more certified" above "less certified" for common names.
  if (upper.includes("CERTIFIED") || upper.includes("VERIFIED") || upper.includes("TRUSTED")) {
    return {
      raw,
      label: raw,
      tier: 3,
      className: "bg-[--app-control-active-bg] text-[--app-fg] ring-1 ring-[--app-accent]",
    };
  }

  if (upper.includes("ATTEST") || upper.includes("SIGNED")) {
    return {
      raw,
      label: raw,
      tier: 2,
      className: "bg-sky-500/10 text-sky-100 ring-1 ring-sky-400/20",
    };
  }

  return {
    raw,
    label: raw,
    tier: 1,
    className: "bg-[--app-surface] text-[--app-fg] ring-1 ring-[--app-surface-ring]",
  };
}

function toolSearchHaystack(tool: RegistryToolListing): string {
  const parts: string[] = [];
  if (tool.display_name) parts.push(tool.display_name);
  if (tool.tool_name) parts.push(tool.tool_name);
  if (tool.description) parts.push(tool.description);
  if (Array.isArray(tool.categories) && tool.categories.length > 0) {
    parts.push(tool.categories.join(" "));
  }
  if (tool.publisher_id) parts.push(tool.publisher_id);
  return normalizeText(parts.join(" "));
}

export function ToolsCatalog({ tools }: Props) {
  const [query, setQuery] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<SortMode>("certification_desc");

  const allCategories = useMemo(() => {
    const bag = new Set<string>();
    for (const tool of tools) {
      if (!Array.isArray(tool.categories)) continue;
      for (const cat of tool.categories) {
        const trimmed = (cat ?? "").trim();
        if (trimmed) bag.add(trimmed);
      }
    }
    return Array.from(bag).sort((a, b) => a.localeCompare(b));
  }, [tools]);

  const normalizedQuery = useMemo(() => normalizeText(query), [query]);

  const filtered = useMemo(() => {
    const activeCategories = new Set(selectedCategories);
    const hasQuery = normalizedQuery.length > 0;
    const hasCategories = activeCategories.size > 0;

    const results: RegistryToolListing[] = [];
    for (const tool of tools) {
      if (hasCategories) {
        const cats = Array.isArray(tool.categories) ? tool.categories : [];
        const matches = cats.some((c) => activeCategories.has(String(c)));
        if (!matches) continue;
      }
      if (hasQuery) {
        const hay = toolSearchHaystack(tool);
        if (!hay.includes(normalizedQuery)) continue;
      }
      results.push(tool);
    }

    results.sort((a, b) => {
      if (sortMode === "name_asc") {
        const aName = a.display_name ?? a.tool_name;
        const bName = b.display_name ?? b.tool_name;
        return aName.localeCompare(bName);
      }

      const aCert = certificationInfo(a.certification_level);
      const bCert = certificationInfo(b.certification_level);
      if (aCert.tier !== bCert.tier) return bCert.tier - aCert.tier;

      const aName = a.display_name ?? a.tool_name;
      const bName = b.display_name ?? b.tool_name;
      return aName.localeCompare(bName);
    });

    return results;
  }, [tools, normalizedQuery, selectedCategories, sortMode]);

  const hasActiveFilters = normalizedQuery.length > 0 || selectedCategories.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-3xl bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex-1">
            <label className="sr-only" htmlFor="tool-search">
              Search tools
            </label>
            <input
              id="tool-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tools by name, description, category, publisher…"
              className="w-full rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-4 py-2 text-[12px] text-[--app-fg] outline-none transition focus:border-[--app-accent] focus:ring-1 focus:ring-[--app-accent]"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as SortMode)}
              className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[11px] text-[--app-fg] outline-none transition focus:border-[--app-accent] focus:ring-1 focus:ring-[--app-accent]"
            >
              <option value="certification_desc">Sort: Certification</option>
              <option value="name_asc">Sort: Name A→Z</option>
            </select>

            {hasActiveFilters ? (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setSelectedCategories([]);
                }}
                className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[11px] font-medium text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
              >
                Clear
              </button>
            ) : null}

            <span className="text-[11px] text-[--app-muted]">
              {filtered.length} result{filtered.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>

        {allCategories.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Categories
            </span>
            <div className="flex flex-wrap gap-2">
              {allCategories.map((cat) => {
                const selected = selectedCategories.includes(cat);
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => {
                      setSelectedCategories((current) => {
                        if (current.includes(cat)) return current.filter((c) => c !== cat);
                        return [...current, cat];
                      });
                    }}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium ring-1 transition ${
                      selected
                        ? "bg-[--app-control-active-bg] text-[--app-fg] ring-[--app-accent]"
                        : "bg-[--app-control-bg] text-[--app-muted] ring-[--app-surface-ring] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <p className="text-[12px] text-[--app-muted]">No tools match your filters.</p>
          {hasActiveFilters ? (
            <p className="mt-2 text-[11px] text-[--app-muted]">
              Try clearing filters or searching by a shorter term.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((tool) => {
            const cert = certificationInfo(tool.certification_level);
            return (
              <Link
                key={tool.tool_name}
                href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring] transition hover:border-[--app-accent] hover:ring-[--app-accent]"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-[--app-fg]">
                      {tool.display_name ?? tool.tool_name}
                    </h2>
                    <p className="truncate text-[10px] text-[--app-muted]">{tool.tool_name}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${cert.className}`}
                    title={cert.raw ?? "Unrated"}
                  >
                    {cert.label}
                  </span>
                </div>

                <p className="line-clamp-3 text-[11px] leading-relaxed text-[--app-muted]">
                  {tool.description ?? "No description provided."}
                </p>

                {Array.isArray(tool.categories) && tool.categories.length > 0 ? (
                  <div className="mt-auto flex flex-wrap items-center gap-2 pt-2 text-[10px] text-[--app-muted]">
                    {tool.categories.slice(0, 4).map((cat: string) => (
                      <span
                        key={cat}
                        className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-medium text-[--app-fg]"
                      >
                        {cat}
                      </span>
                    ))}
                    {tool.categories.length > 4 ? (
                      <span className="text-[10px] text-[--app-muted]">
                        +{tool.categories.length - 4}
                      </span>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-auto pt-2 text-[10px] text-[--app-muted]">No categories</div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}


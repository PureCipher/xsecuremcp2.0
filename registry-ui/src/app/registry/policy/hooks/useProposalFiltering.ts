"use client";

import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import type { PolicyProposalItem } from "@/lib/registryClient";

export type ProposalFilterKey =
  | "all"
  | "assigned"
  | "unassigned"
  | "stale"
  | "ready"
  | "needs_simulation";

const TERMINAL_STATUSES = new Set(["deployed", "rejected", "withdrawn"]);

export function useProposalFiltering({
  proposals,
  currentUsername,
  requireSimulation,
}: {
  proposals: PolicyProposalItem[];
  currentUsername?: string | null;
  requireSimulation: boolean;
}) {
  const [filterKey, setFilterKey] = useState<ProposalFilterKey>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleSearchChange = useCallback((value: string) => {
    setSearchTerm(value);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebouncedSearch(value), 200);
  }, []);

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  const sorted = useMemo(
    () =>
      proposals.slice().sort((left, right) => {
        const rightTime = Date.parse(right.created_at ?? "") || 0;
        const leftTime = Date.parse(left.created_at ?? "") || 0;
        return rightTime - leftTime;
      }),
    [proposals],
  );

  const activeProposals = useMemo(
    () => sorted.filter((p) => !TERMINAL_STATUSES.has(p.status ?? "")),
    [sorted],
  );

  const historyProposals = useMemo(
    () => sorted.filter((p) => TERMINAL_STATUSES.has(p.status ?? "")),
    [sorted],
  );

  const counts = useMemo(
    () => ({
      all: activeProposals.length,
      assigned: activeProposals.filter(
        (p) => p.assigned_reviewer === currentUsername,
      ).length,
      unassigned: activeProposals.filter((p) => !p.assigned_reviewer).length,
      stale: activeProposals.filter((p) => p.is_stale).length,
      ready: activeProposals.filter(
        (p) =>
          p.status === "simulated" ||
          (!requireSimulation && p.status === "validated"),
      ).length,
      needs_simulation: activeProposals.filter(
        (p) =>
          requireSimulation &&
          p.validation?.valid !== false &&
          p.status === "validated",
      ).length,
    }),
    [activeProposals, currentUsername, requireSimulation],
  );

  const filteredProposals = useMemo(() => {
    const query = debouncedSearch.trim().toLowerCase();
    return activeProposals.filter((proposal) => {
      const filterMatch =
        filterKey === "all"
          ? true
          : filterKey === "assigned"
            ? proposal.assigned_reviewer === currentUsername
            : filterKey === "unassigned"
              ? !proposal.assigned_reviewer
              : filterKey === "stale"
                ? proposal.is_stale === true
                : filterKey === "ready"
                  ? proposal.status === "simulated" ||
                    (!requireSimulation && proposal.status === "validated")
                  : requireSimulation &&
                    proposal.validation?.valid !== false &&
                    proposal.status === "validated";

      if (!filterMatch) return false;
      if (!query) return true;

      return [
        proposal.description,
        proposal.author,
        proposal.action,
        proposal.assigned_reviewer,
        proposal.proposal_id,
      ]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(query));
    });
  }, [activeProposals, currentUsername, filterKey, debouncedSearch, requireSimulation]);

  return {
    filterKey,
    setFilterKey,
    searchTerm,
    setSearchTerm: handleSearchChange,
    filteredProposals,
    historyProposals,
    counts,
    activeProposalCount: activeProposals.length,
  };
}

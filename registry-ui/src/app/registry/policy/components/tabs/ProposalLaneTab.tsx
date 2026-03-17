"use client";

import { useState } from "react";
import type {
  PolicyProposalItem,
  PolicyProposalEvent,
  PolicySimulationScenario,
} from "@/lib/registryClient";
import { usePolicyContext } from "../../contexts/PolicyContext";
import {
  useProposalFiltering,
  type ProposalFilterKey,
} from "../../hooks/useProposalFiltering";
import { ConfirmModal } from "../ConfirmModal";

type ProposalLaneTabProps = {
  proposals: PolicyProposalItem[];
  requireApproval: boolean;
  requireSimulation: boolean;
  simulationDefaults: PolicySimulationScenario[];
  onSimulate: (proposalId: string, scenarios: PolicySimulationScenario[]) => Promise<void>;
  onApproveAndDeploy: (
    proposal: PolicyProposalItem,
    note: string,
    requireApproval: boolean,
    requireSimulation: boolean,
  ) => Promise<void>;
  onReject: (proposalId: string, reason: string) => Promise<void>;
  onWithdraw: (proposalId: string, note: string) => Promise<void>;
  onAssign: (proposalId: string, reviewer: string, note: string) => Promise<void>;
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function proposalStatusLabel(status: string | undefined): string {
  switch (status) {
    case "draft": return "Draft";
    case "validated": return "Ready for approval";
    case "validation_failed": return "Needs fixes";
    case "simulated": return "Simulated";
    case "approved": return "Approved";
    case "deployed": return "Live";
    case "rejected": return "Rejected";
    case "withdrawn": return "Withdrawn";
    default: return "Proposal";
  }
}

function proposalStatusClass(status: string | undefined): string {
  switch (status) {
    case "validated":
    case "simulated":
    case "approved":
    case "deployed":
      return "bg-emerald-500/15 text-emerald-100 ring-emerald-400/60";
    case "validation_failed":
    case "rejected":
      return "bg-rose-500/15 text-rose-100 ring-rose-400/60";
    case "withdrawn":
      return "bg-zinc-500/15 text-zinc-100 ring-zinc-400/50";
    default:
      return "bg-amber-500/15 text-amber-100 ring-amber-400/60";
  }
}

function actionLabel(action: string | undefined): string {
  switch (action) {
    case "add": return "Add rule";
    case "swap": return "Change rule";
    case "remove": return "Remove rule";
    case "replace_chain": return "Replace policy chain";
    default: return "Policy change";
  }
}

function trailEventLabel(event: string | undefined): string {
  const raw = (event ?? "").trim();
  if (!raw) return "Policy event";
  return raw
    .split("_")
    .map((segment) =>
      segment ? `${segment[0].toUpperCase()}${segment.slice(1)}` : segment,
    )
    .join(" ");
}

export function ProposalLaneTab({
  proposals,
  requireApproval,
  requireSimulation,
  simulationDefaults,
  onSimulate,
  onApproveAndDeploy,
  onReject,
  onWithdraw,
  onAssign,
}: ProposalLaneTabProps) {
  const { busyKey, currentUsername } = usePolicyContext();
  const {
    filterKey,
    setFilterKey,
    searchTerm,
    setSearchTerm,
    filteredProposals,
    historyProposals,
    counts,
    activeProposalCount,
  } = useProposalFiltering({ proposals, currentUsername, requireSimulation });

  const [proposalNotes, setProposalNotes] = useState<Record<string, string>>({});
  const [assignmentTargets, setAssignmentTargets] = useState<Record<string, string>>({});

  // Destructive action modals
  const [deployModal, setDeployModal] = useState<PolicyProposalItem | null>(null);
  const [rejectModal, setRejectModal] = useState<string | null>(null);
  const [withdrawModal, setWithdrawModal] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
            Proposal lane
          </p>
          <h2 className="text-xl font-semibold text-emerald-50">
            Review changes before they go live
          </h2>
          <p className="max-w-2xl text-xs text-emerald-100/80">
            Drafts land here first. Approve and apply ready proposals, or reject and
            withdraw them when they should not ship.
          </p>
        </div>

        {requireSimulation ? (
          <div className="mt-4 rounded-2xl bg-amber-500/10 p-4 ring-1 ring-amber-400/40">
            <p className="text-xs text-amber-100">
              This workspace requires a quick simulation before approval. Each
              proposal can be tested against the registry&apos;s default access scenarios
              before it is applied.
            </p>
          </div>
        ) : null}

        {/* Filter bar */}
        <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ["all", "All"],
                  ["assigned", "Assigned to me"],
                  ["unassigned", "Unassigned"],
                  ["ready", "Ready to approve"],
                  ["needs_simulation", "Needs simulation"],
                  ["stale", "Stale"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilterKey(key)}
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${
                    filterKey === key
                      ? "bg-emerald-500 text-emerald-950"
                      : "border border-emerald-700/70 text-emerald-100 hover:bg-emerald-700/20"
                  }`}
                >
                  {label} · {counts[key]}
                </button>
              ))}
            </div>
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search proposals, owners, or actions"
              className="w-full max-w-xs rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            />
          </div>
        </div>

        {/* Active proposals */}
        <div className="mt-4 flex flex-col gap-3">
          {filteredProposals.length === 0 ? (
            <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
              <p className="text-xs text-emerald-100/90">
                {activeProposalCount === 0
                  ? "No policy changes are waiting right now. Draft a change from the Live Chain or Tools tab."
                  : "No proposals match the current reviewer filter."}
              </p>
            </div>
          ) : (
            filteredProposals.map((proposal) => {
              const proposalId = proposal.proposal_id ?? "";
              const validationFindings = proposal.validation?.findings ?? [];
              const simulationResults = proposal.simulation?.results ?? [];
              const simulationSummary = proposal.simulation;
              const assignmentValue =
                assignmentTargets[proposalId] ??
                proposal.assigned_reviewer ??
                currentUsername ??
                "";
              const decisionTrail = (proposal.decision_trail ?? [])
                .slice()
                .reverse()
                .slice(0, 4);
              const canApplyDirectly =
                !proposal.is_stale &&
                !requireApproval &&
                (proposal.status === "validated" || proposal.status === "simulated");
              const canApproveAndApply =
                !proposal.is_stale &&
                requireApproval &&
                (proposal.status === "validated" || proposal.status === "simulated");
              const canDeploy = !proposal.is_stale && proposal.status === "approved";
              const needsSimulation =
                !proposal.is_stale &&
                requireSimulation &&
                proposal.status !== "simulated" &&
                proposal.status !== "approved";

              return (
                <article
                  key={proposalId}
                  className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ring-1 ${proposalStatusClass(
                            proposal.status,
                          )}`}
                        >
                          {proposalStatusLabel(proposal.status)}
                        </span>
                        {proposal.is_stale ? (
                          <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-rose-100 ring-1 ring-rose-400/60">
                            Out of date
                          </span>
                        ) : null}
                        <span className="text-xs font-semibold text-emerald-50">
                          {actionLabel(proposal.action)}
                        </span>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-emerald-100/90">
                          {proposal.description || "No reason captured for this proposal."}
                        </p>
                        <p className="text-[11px] text-emerald-300/90">
                          Proposed by {proposal.author ?? "unknown"} ·{" "}
                          {formatTimestamp(proposal.created_at)}
                        </p>
                        <p className="text-[11px] text-emerald-300/90">
                          Owner: {proposal.assigned_reviewer ?? "Unassigned"}
                        </p>
                        <p className="text-[11px] text-emerald-300/90">
                          Drafted for v{proposal.base_version_number ?? "?"} · live v
                          {proposal.live_version_number ?? "?"}
                        </p>
                        {proposal.replacement_provider_count ? (
                          <p className="text-[11px] text-emerald-200/90">
                            Imported chain: {proposal.replacement_provider_count}{" "}
                            {proposal.replacement_provider_count === 1
                              ? "step"
                              : "steps"}
                          </p>
                        ) : null}
                        {proposal.provider?.summary ? (
                          <p className="text-[11px] text-emerald-200/90">
                            Draft: {proposal.provider.summary}
                          </p>
                        ) : null}
                        {proposal.target_index !== null &&
                        proposal.target_index !== undefined ? (
                          <p className="text-[11px] text-emerald-200/90">
                            Applies to step {proposal.target_index + 1}
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          void onAssign(
                            proposalId,
                            currentUsername ?? "",
                            proposalNotes[proposalId] ?? "",
                          )
                        }
                        disabled={
                          !currentUsername ||
                          busyKey === `assign-${proposalId}` ||
                          proposal.assigned_reviewer === currentUsername
                        }
                        className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                      >
                        {busyKey === `assign-${proposalId}`
                          ? "Assigning\u2026"
                          : proposal.assigned_reviewer === currentUsername
                            ? "Assigned to you"
                            : "Assign to me"}
                      </button>
                      {needsSimulation ? (
                        <button
                          type="button"
                          onClick={() => void onSimulate(proposalId, simulationDefaults)}
                          disabled={busyKey === `simulate-${proposalId}`}
                          className="rounded-full border border-amber-400/80 px-3 py-1 text-[11px] font-semibold text-amber-100 transition hover:bg-amber-400/10 disabled:opacity-60"
                        >
                          {busyKey === `simulate-${proposalId}`
                            ? "Running\u2026"
                            : "Run simulation"}
                        </button>
                      ) : null}
                      {canApproveAndApply ? (
                        <button
                          type="button"
                          onClick={() => setDeployModal(proposal)}
                          disabled={busyKey === `approve-${proposalId}`}
                          className="rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
                        >
                          {busyKey === `approve-${proposalId}`
                            ? "Applying\u2026"
                            : "Approve & apply"}
                        </button>
                      ) : null}
                      {canApplyDirectly || canDeploy ? (
                        <button
                          type="button"
                          onClick={() => setDeployModal(proposal)}
                          disabled={busyKey === `approve-${proposalId}`}
                          className="rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
                        >
                          {busyKey === `approve-${proposalId}`
                            ? "Applying\u2026"
                            : "Apply live"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => setWithdrawModal(proposalId)}
                        disabled={busyKey === `withdraw-${proposalId}`}
                        className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                      >
                        {busyKey === `withdraw-${proposalId}`
                          ? "Withdrawing\u2026"
                          : "Withdraw"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectModal(proposalId)}
                        disabled={busyKey === `reject-${proposalId}`}
                        className="rounded-full border border-rose-500/80 px-3 py-1 text-[11px] font-semibold text-rose-100 transition hover:bg-rose-500/10 disabled:opacity-60"
                      >
                        {busyKey === `reject-${proposalId}`
                          ? "Rejecting\u2026"
                          : "Reject"}
                      </button>
                    </div>
                  </div>

                  {proposal.is_stale ? (
                    <div className="mt-3 rounded-2xl bg-rose-500/10 p-3 ring-1 ring-rose-400/40">
                      <p className="text-xs text-rose-100">
                        This proposal was drafted against version{" "}
                        {proposal.base_version_number ?? "?"}, but the live policy
                        chain is now on version {proposal.live_version_number ?? "?"}.
                        Create a fresh proposal from the current chain before you
                        simulate or apply it.
                      </p>
                    </div>
                  ) : null}

                  <div className="mt-3 grid gap-3 lg:grid-cols-[0.95fr,1fr,0.9fr]">
                    {/* Ownership panel */}
                    <div className="rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                        Ownership
                      </p>
                      <p className="mt-2 text-xs text-emerald-100/90">
                        {proposal.assigned_reviewer
                          ? `Currently owned by ${proposal.assigned_reviewer}.`
                          : "No owner yet. Assign someone before final approval if you want a clear reviewer."}
                      </p>
                      <div className="mt-3 flex flex-col gap-2">
                        <input
                          value={assignmentValue}
                          onChange={(event) =>
                            setAssignmentTargets((current) => ({
                              ...current,
                              [proposalId]: event.target.value,
                            }))
                          }
                          placeholder="Reviewer username"
                          className="w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
                        />
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              void onAssign(
                                proposalId,
                                assignmentValue,
                                proposalNotes[proposalId] ?? "",
                              )
                            }
                            disabled={busyKey === `assign-${proposalId}`}
                            className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                          >
                            {busyKey === `assign-${proposalId}`
                              ? "Assigning\u2026"
                              : "Save owner"}
                          </button>
                          {currentUsername ? (
                            <button
                              type="button"
                              onClick={() =>
                                setAssignmentTargets((current) => ({
                                  ...current,
                                  [proposalId]: currentUsername,
                                }))
                              }
                              className="rounded-full border border-emerald-700/70 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/20"
                            >
                              Fill with my username
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    {/* Review note */}
                    <div className="rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                        Review note
                      </p>
                      <input
                        value={proposalNotes[proposalId] ?? ""}
                        onChange={(event) =>
                          setProposalNotes((current) => ({
                            ...current,
                            [proposalId]: event.target.value,
                          }))
                        }
                        placeholder="Optional note for reject or follow-up"
                        className="mt-2 w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
                      />
                    </div>

                    {/* Validation */}
                    <div className="rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                        Validation
                      </p>
                      <p className="mt-2 text-xs text-emerald-100/90">
                        {proposal.validation?.valid === false
                          ? "This proposal needs fixes before it can be approved."
                          : "This proposal is structurally ready to move forward."}
                      </p>
                      {validationFindings.length > 0 ? (
                        <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
                          {validationFindings.slice(0, 3).map((finding, index) => (
                            <li key={`${proposalId}-finding-${index}`}>
                              {finding.severity?.toUpperCase()}: {finding.message}
                            </li>
                          ))}
                          {validationFindings.length > 3 ? (
                            <li>
                              +{validationFindings.length - 3} more validation findings
                            </li>
                          ) : null}
                        </ul>
                      ) : null}
                    </div>
                  </div>

                  {/* Decision trail */}
                  {decisionTrail.length > 0 ? (
                    <div className="mt-3 rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                          Decision trail
                        </p>
                        <p className="text-[11px] text-emerald-200/90">
                          {proposal.decision_trail?.length ?? 0} recorded steps
                        </p>
                      </div>
                      <ol className="mt-3 space-y-2">
                        {decisionTrail.map((event: PolicyProposalEvent, index) => (
                          <li
                            key={`${proposalId}-trail-${event.created_at ?? index}`}
                            className="rounded-2xl bg-emerald-950/60 p-3 ring-1 ring-emerald-700/30"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-semibold text-emerald-50">
                                {trailEventLabel(event.event)}
                              </p>
                              <p className="text-[11px] text-emerald-300/90">
                                {formatTimestamp(event.created_at)}
                              </p>
                            </div>
                            <p className="mt-1 text-[11px] text-emerald-300/90">
                              {event.actor ?? "unknown"}
                            </p>
                            {event.note ? (
                              <p className="mt-2 text-xs text-emerald-100/90">
                                {event.note}
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}

                  {/* Imported chain preview */}
                  {proposal.provider_set?.length ? (
                    <div className="mt-3 rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                          Imported chain preview
                        </p>
                        <p className="text-[11px] text-emerald-200/90">
                          {proposal.provider_set.length}{" "}
                          {proposal.provider_set.length === 1 ? "step" : "steps"}
                        </p>
                      </div>
                      <ul className="mt-3 space-y-2">
                        {proposal.provider_set.slice(0, 4).map((providerItem) => (
                          <li
                            key={`${proposalId}-provider-set-${providerItem.index}`}
                            className="rounded-2xl bg-emerald-950/60 p-3 ring-1 ring-emerald-700/30"
                          >
                            <p className="text-xs font-semibold text-emerald-50">
                              Step {providerItem.index + 1}: {providerItem.type}
                            </p>
                            <p className="mt-1 text-[11px] text-emerald-300/90">
                              {providerItem.summary}
                            </p>
                          </li>
                        ))}
                        {proposal.provider_set.length > 4 ? (
                          <li className="text-[11px] text-emerald-200/90">
                            +{proposal.provider_set.length - 4} more imported steps
                          </li>
                        ) : null}
                      </ul>
                    </div>
                  ) : null}

                  {/* Simulation results */}
                  {simulationSummary ? (
                    <div className="mt-3 rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/40">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                          Simulation
                        </p>
                        <p className="text-[11px] text-emerald-200/90">
                          {simulationSummary.allowed ?? 0} allowed ·{" "}
                          {simulationSummary.denied ?? 0} denied ·{" "}
                          {simulationSummary.errors ?? 0} errors
                        </p>
                      </div>
                      <p className="mt-2 text-xs text-emerald-100/90">
                        Tested against {simulationSummary.total ?? 0} registry access
                        scenarios.
                      </p>
                      {simulationResults.length > 0 ? (
                        <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
                          {simulationResults.slice(0, 4).map((result, index) => (
                            <li key={`${proposalId}-simulation-${index}`}>
                              {result.label || result.resource_id || "Scenario"}:{" "}
                              {(result.decision || "unknown").toUpperCase()} ·{" "}
                              {result.reason || "No reason captured."}
                            </li>
                          ))}
                          {simulationResults.length > 4 ? (
                            <li>
                              +{simulationResults.length - 4} more simulated outcomes
                            </li>
                          ) : null}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })
          )}
        </div>

        {/* History */}
        {historyProposals.length > 0 ? (
          <div className="mt-5 rounded-2xl bg-emerald-950/60 p-4 ring-1 ring-emerald-700/60">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
              Recent decisions
            </p>
            <div className="mt-3 flex flex-col gap-2">
              {historyProposals.slice(0, 4).map((proposal) => (
                <div
                  key={`history-${proposal.proposal_id ?? "unknown"}`}
                  className="rounded-2xl bg-emerald-900/20 p-3 ring-1 ring-emerald-700/30"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ring-1 ${proposalStatusClass(
                        proposal.status,
                      )}`}
                    >
                      {proposalStatusLabel(proposal.status)}
                    </span>
                    <span className="text-xs font-semibold text-emerald-50">
                      {actionLabel(proposal.action)}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-emerald-100/90">
                    {proposal.description || "No description recorded."}
                  </p>
                  <p className="mt-1 text-[11px] text-emerald-300/90">
                    {proposal.status === "deployed"
                      ? `Went live ${formatTimestamp(proposal.deployed_at)}`
                      : proposal.status === "rejected"
                        ? `Rejected ${proposal.rejection_reason ? `— ${proposal.rejection_reason}` : ""}`
                        : `Withdrawn ${formatTimestamp(proposal.created_at)}`}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {/* Deploy confirmation modal */}
      <ConfirmModal
        isOpen={deployModal !== null}
        title="Apply this proposal to the live chain?"
        description={
          deployModal
            ? `This will deploy the "${actionLabel(deployModal.action)}" proposal to the live policy chain.`
            : ""
        }
        confirmLabel={requireApproval ? "Approve & apply" : "Apply live"}
        isDangerous={false}
        isLoading={
          deployModal !== null &&
          busyKey === `approve-${deployModal.proposal_id}`
        }
        onConfirm={async () => {
          if (!deployModal) return;
          await onApproveAndDeploy(
            deployModal,
            proposalNotes[deployModal.proposal_id ?? ""] ?? "",
            requireApproval,
            requireSimulation,
          );
          setDeployModal(null);
        }}
        onCancel={() => setDeployModal(null)}
      />

      {/* Reject confirmation modal */}
      <ConfirmModal
        isOpen={rejectModal !== null}
        title="Reject this proposal?"
        description="The proposal will be moved to the decision history. This action cannot be undone."
        confirmLabel="Reject proposal"
        isDangerous
        isLoading={rejectModal !== null && busyKey === `reject-${rejectModal}`}
        onConfirm={async () => {
          if (!rejectModal) return;
          await onReject(rejectModal, proposalNotes[rejectModal] ?? "");
          setRejectModal(null);
        }}
        onCancel={() => setRejectModal(null)}
      >
        <input
          value={proposalNotes[rejectModal ?? ""] ?? ""}
          onChange={(event) =>
            setProposalNotes((current) => ({
              ...current,
              [rejectModal ?? ""]: event.target.value,
            }))
          }
          placeholder="Rejection reason"
          className="w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
        />
      </ConfirmModal>

      {/* Withdraw confirmation modal */}
      <ConfirmModal
        isOpen={withdrawModal !== null}
        title="Withdraw this proposal?"
        description="The proposal will be archived. You can always create a new one."
        confirmLabel="Withdraw"
        isDangerous={false}
        isLoading={withdrawModal !== null && busyKey === `withdraw-${withdrawModal}`}
        onConfirm={async () => {
          if (!withdrawModal) return;
          await onWithdraw(withdrawModal, proposalNotes[withdrawModal] ?? "");
          setWithdrawModal(null);
        }}
        onCancel={() => setWithdrawModal(null)}
      />
    </div>
  );
}

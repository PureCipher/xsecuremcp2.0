"use client";

import { useState } from "react";
import type { PolicyProposalEvent, PolicyProposalItem, PolicySimulationScenario } from "@/lib/registryClient";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  TextField,
  Typography,
} from "@mui/material";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { useProposalFiltering } from "../../hooks/useProposalFiltering";
import { ProposalStepper } from "../ProposalStepper";
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
    case "draft":
      return "Draft";
    case "validated":
      return "Ready for approval";
    case "validation_failed":
      return "Needs fixes";
    case "simulated":
      return "Simulated";
    case "approved":
      return "Approved";
    case "deployed":
      return "Live";
    case "rejected":
      return "Rejected";
    case "withdrawn":
      return "Withdrawn";
    default:
      return "Proposal";
  }
}

function proposalStatusSx(status: string | undefined): Record<string, unknown> {
  switch (status) {
    case "validated":
    case "simulated":
    case "approved":
    case "deployed":
      return { bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", border: "1px solid var(--app-accent)" };
    case "validation_failed":
    case "rejected":
      return { bgcolor: "rgba(244, 63, 94, 0.12)", color: "rgb(255, 228, 230)", border: "1px solid rgba(251, 113, 133, 0.55)" };
    case "withdrawn":
      return { bgcolor: "rgba(113, 113, 122, 0.12)", color: "rgb(244, 244, 245)", border: "1px solid rgba(161, 161, 170, 0.45)" };
    default:
      return { bgcolor: "rgba(245, 158, 11, 0.12)", color: "rgb(254, 243, 199)", border: "1px solid rgba(251, 191, 36, 0.55)" };
  }
}

function actionLabel(action: string | undefined): string {
  switch (action) {
    case "add":
      return "Add rule";
    case "swap":
      return "Change rule";
    case "remove":
      return "Remove rule";
    case "replace_chain":
      return "Replace policy chain";
    default:
      return "Policy change";
  }
}

function trailEventLabel(event: string | undefined): string {
  const raw = (event ?? "").trim();
  if (!raw) return "Policy event";
  return raw
    .split("_")
    .map((segment) => (segment ? `${segment[0].toUpperCase()}${segment.slice(1)}` : segment))
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
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  function toggleCard(proposalId: string) {
    setExpandedCards((current) => ({
      ...current,
      [proposalId]: !current[proposalId],
    }));
  }

  const [deployModal, setDeployModal] = useState<PolicyProposalItem | null>(null);
  const [rejectModal, setRejectModal] = useState<string | null>(null);
  const [withdrawModal, setWithdrawModal] = useState<string | null>(null);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Proposal lane
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Review changes before they go live
            </Typography>
            <Typography sx={{ maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
              Drafts land here first. Approve and apply ready proposals, or reject and withdraw them when they should not ship.
            </Typography>
          </Box>

          {requireSimulation ? (
            <Alert
              severity="warning"
              sx={{
                mt: 2,
                borderRadius: 3,
                bgcolor: "rgba(245, 158, 11, 0.12)",
                border: "1px solid rgba(251, 191, 36, 0.35)",
                color: "rgb(253, 230, 138)",
              }}
            >
              This workspace requires a quick simulation before approval. Each proposal can be tested against the registry&apos;s default access scenarios before it is applied.
            </Alert>
          ) : null}

          <Card variant="outlined" sx={{ mt: 2, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
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
                    <Button
                      key={key}
                      type="button"
                      size="small"
                      variant={filterKey === key ? "contained" : "outlined"}
                      onClick={() => setFilterKey(key)}
                      sx={{
                        borderRadius: 999,
                        textTransform: "none",
                        fontSize: 11,
                        fontWeight: 800,
                        letterSpacing: "0.12em",
                        ...(filterKey === key
                          ? {}
                          : {
                              borderColor: "var(--app-border)",
                              color: "var(--app-muted)",
                              "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
                            }),
                      }}
                    >
                      {label} · {counts[key]}
                    </Button>
                  ))}
                </Box>
                <TextField
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search proposals, owners, or actions"
                  size="small"
                  sx={{ width: { xs: "100%", sm: 320 } }}
                />
              </Box>
            </CardContent>
          </Card>

          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            {filteredProposals.length === 0 ? (
              <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    {activeProposalCount === 0
                      ? "No policy changes are waiting right now. Draft a change from the Live Chain or Tools tab."
                      : "No proposals match the current reviewer filter."}
                  </Typography>
                </CardContent>
              </Card>
            ) : (
              filteredProposals.map((proposal) => {
                const proposalId = proposal.proposal_id ?? "";
                const validationFindings = proposal.validation?.findings ?? [];
                const simulationResults = proposal.simulation?.results ?? [];
                const simulationSummary = proposal.simulation;
                const assignmentValue =
                  assignmentTargets[proposalId] ?? proposal.assigned_reviewer ?? currentUsername ?? "";
                const decisionTrail = (proposal.decision_trail ?? []).slice().reverse().slice(0, 4);
                const canApplyDirectly =
                  !proposal.is_stale && !requireApproval && (proposal.status === "validated" || proposal.status === "simulated");
                const canApproveAndApply =
                  !proposal.is_stale && requireApproval && (proposal.status === "validated" || proposal.status === "simulated");
                const canDeploy = !proposal.is_stale && proposal.status === "approved";
                const needsSimulation =
                  !proposal.is_stale && requireSimulation && proposal.status !== "simulated" && proposal.status !== "approved";

                const isExpanded = expandedCards[proposalId] ?? false;

                return (
                  <Card key={proposalId} variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                    <Box sx={{ px: 2, pt: 2 }}>
                      <ProposalStepper status={proposal.status} requireSimulation={requireSimulation} />
                    </Box>

                    <CardContent sx={{ p: 2, pt: 1.5 }}>
                      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
                        <Box sx={{ display: "grid", gap: 1, minWidth: 240 }}>
                          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                            <Chip
                              size="small"
                              label={proposalStatusLabel(proposal.status)}
                              sx={{
                                borderRadius: 999,
                                fontSize: 10,
                                fontWeight: 800,
                                textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                height: 22,
                                ...proposalStatusSx(proposal.status),
                              }}
                            />
                            {proposal.is_stale ? (
                              <Chip
                                size="small"
                                label="Out of date"
                                sx={{
                                  borderRadius: 999,
                                  bgcolor: "rgba(244, 63, 94, 0.12)",
                                  color: "rgb(254, 205, 211)",
                                  border: "1px solid rgba(251, 113, 133, 0.45)",
                                  fontSize: 10,
                                  fontWeight: 800,
                                  textTransform: "uppercase",
                                  letterSpacing: "0.12em",
                                }}
                              />
                            ) : null}
                            <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                              {actionLabel(proposal.action)}
                            </Typography>
                          </Box>

                          <Box sx={{ display: "grid", gap: 0.5 }}>
                            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                              {proposal.description || "No reason captured for this proposal."}
                            </Typography>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                              Proposed by {proposal.author ?? "unknown"} · {formatTimestamp(proposal.created_at)}
                            </Typography>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                              Owner: {proposal.assigned_reviewer ?? "Unassigned"}
                            </Typography>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                              Drafted for v{proposal.base_version_number ?? "?"} · live v{proposal.live_version_number ?? "?"}
                            </Typography>
                            {proposal.replacement_provider_count ? (
                              <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                Imported chain: {proposal.replacement_provider_count}{" "}
                                {proposal.replacement_provider_count === 1 ? "step" : "steps"}
                              </Typography>
                            ) : null}
                            {proposal.provider?.summary ? (
                              <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                Draft: {proposal.provider.summary}
                              </Typography>
                            ) : null}
                            {proposal.target_index !== null && proposal.target_index !== undefined ? (
                              <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                Applies to step {proposal.target_index + 1}
                              </Typography>
                            ) : null}
                          </Box>
                        </Box>

                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                          <Button
                            type="button"
                            variant="outlined"
                            size="small"
                            onClick={() => void onAssign(proposalId, currentUsername ?? "", proposalNotes[proposalId] ?? "")}
                            disabled={!currentUsername || busyKey === `assign-${proposalId}` || proposal.assigned_reviewer === currentUsername}
                            sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                          >
                            {busyKey === `assign-${proposalId}`
                              ? "Assigning…"
                              : proposal.assigned_reviewer === currentUsername
                                ? "Assigned to you"
                                : "Assign to me"}
                          </Button>
                          {needsSimulation ? (
                            <Button
                              type="button"
                              variant="outlined"
                              size="small"
                              onClick={() => void onSimulate(proposalId, simulationDefaults)}
                              disabled={busyKey === `simulate-${proposalId}`}
                              sx={{
                                borderRadius: 999,
                                borderColor: "rgba(251, 191, 36, 0.55)",
                                color: "rgb(253, 230, 138)",
                                "&:hover": { bgcolor: "rgba(245, 158, 11, 0.12)", borderColor: "rgba(251, 191, 36, 0.55)" },
                              }}
                            >
                              {busyKey === `simulate-${proposalId}` ? "Running…" : "Run simulation"}
                            </Button>
                          ) : null}
                          {canApproveAndApply ? (
                            <Button
                              type="button"
                              variant="contained"
                              size="small"
                              onClick={() => setDeployModal(proposal)}
                              disabled={busyKey === `approve-${proposalId}`}
                              sx={{ borderRadius: 999 }}
                            >
                              {busyKey === `approve-${proposalId}` ? "Applying…" : "Approve & apply"}
                            </Button>
                          ) : null}
                          {canApplyDirectly || canDeploy ? (
                            <Button
                              type="button"
                              variant="contained"
                              size="small"
                              onClick={() => setDeployModal(proposal)}
                              disabled={busyKey === `approve-${proposalId}`}
                              sx={{ borderRadius: 999 }}
                            >
                              {busyKey === `approve-${proposalId}` ? "Applying…" : "Apply live"}
                            </Button>
                          ) : null}
                          <Button
                            type="button"
                            variant="outlined"
                            size="small"
                            onClick={() => setWithdrawModal(proposalId)}
                            disabled={busyKey === `withdraw-${proposalId}`}
                            sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                          >
                            {busyKey === `withdraw-${proposalId}` ? "Withdrawing…" : "Withdraw"}
                          </Button>
                          <Button
                            type="button"
                            variant="outlined"
                            size="small"
                            onClick={() => setRejectModal(proposalId)}
                            disabled={busyKey === `reject-${proposalId}`}
                            sx={{
                              borderRadius: 999,
                              borderColor: "rgba(251, 113, 133, 0.55)",
                              color: "rgb(254, 205, 211)",
                              "&:hover": { bgcolor: "rgba(244, 63, 94, 0.12)", borderColor: "rgba(251, 113, 133, 0.55)" },
                            }}
                          >
                            {busyKey === `reject-${proposalId}` ? "Rejecting…" : "Reject"}
                          </Button>
                        </Box>
                      </Box>

                      {proposal.is_stale ? (
                        <Alert
                          severity="error"
                          sx={{
                            mt: 2,
                            borderRadius: 3,
                            bgcolor: "rgba(244, 63, 94, 0.12)",
                            border: "1px solid rgba(251, 113, 133, 0.35)",
                            color: "rgb(254, 205, 211)",
                          }}
                        >
                          This proposal was drafted against version {proposal.base_version_number ?? "?"}, but the live policy chain is now on version{" "}
                          {proposal.live_version_number ?? "?"}. Create a fresh proposal from the current chain before you simulate or apply it.
                        </Alert>
                      ) : null}

                      <Button
                        type="button"
                        variant="text"
                        size="small"
                        onClick={() => toggleCard(proposalId)}
                        sx={{ mt: 2, px: 0, color: "var(--app-muted)", "&:hover": { color: "var(--app-fg)" } }}
                      >
                        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
                          <Box
                            component="svg"
                            viewBox="0 0 12 12"
                            sx={{ width: 12, height: 12, transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 160ms ease" }}
                            fill="currentColor"
                          >
                            <path d="M4 2l4 4-4 4V2z" />
                          </Box>
                          <Typography component="span" sx={{ fontSize: 11, fontWeight: 800 }}>
                            {isExpanded ? "Hide details" : "Show details"}
                          </Typography>
                        </Box>
                      </Button>

                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,0.95fr) minmax(0,1fr) minmax(0,0.9fr)" } }}>
                          <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                Ownership
                              </Typography>
                              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                {proposal.assigned_reviewer
                                  ? `Currently owned by ${proposal.assigned_reviewer}.`
                                  : "No owner yet. Assign someone before final approval if you want a clear reviewer."}
                              </Typography>
                              <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
                                <TextField
                                  value={assignmentValue}
                                  onChange={(event) =>
                                    setAssignmentTargets((current) => ({
                                      ...current,
                                      [proposalId]: event.target.value,
                                    }))
                                  }
                                  placeholder="Reviewer username"
                                  size="small"
                                  fullWidth
                                />
                                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                                  <Button
                                    type="button"
                                    variant="outlined"
                                    size="small"
                                    onClick={() => void onAssign(proposalId, assignmentValue, proposalNotes[proposalId] ?? "")}
                                    disabled={busyKey === `assign-${proposalId}`}
                                    sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                                  >
                                    {busyKey === `assign-${proposalId}` ? "Assigning…" : "Save owner"}
                                  </Button>
                                  {currentUsername ? (
                                    <Button
                                      type="button"
                                      variant="outlined"
                                      size="small"
                                      onClick={() =>
                                        setAssignmentTargets((current) => ({
                                          ...current,
                                          [proposalId]: currentUsername,
                                        }))
                                      }
                                      sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                                    >
                                      Fill with my username
                                    </Button>
                                  ) : null}
                                </Box>
                              </Box>
                            </CardContent>
                          </Card>

                          <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                Review note
                              </Typography>
                              <TextField
                                value={proposalNotes[proposalId] ?? ""}
                                onChange={(event) =>
                                  setProposalNotes((current) => ({
                                    ...current,
                                    [proposalId]: event.target.value,
                                  }))
                                }
                                placeholder="Optional note for reject or follow-up"
                                size="small"
                                fullWidth
                                sx={{ mt: 1 }}
                              />
                            </CardContent>
                          </Card>

                          <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                Validation
                              </Typography>
                              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                {proposal.validation?.valid === false
                                  ? "This proposal needs fixes before it can be approved."
                                  : "This proposal is structurally ready to move forward."}
                              </Typography>
                              {validationFindings.length > 0 ? (
                                <Box component="ul" sx={{ listStyle: "disc", pl: 2, mt: 1, mb: 0, color: "var(--app-muted)", fontSize: 11, display: "grid", gap: 0.5 }}>
                                  {validationFindings.slice(0, 3).map((finding, index) => (
                                    <li key={`${proposalId}-finding-${index}`}>
                                      {finding.severity?.toUpperCase()}: {finding.message}
                                    </li>
                                  ))}
                                  {validationFindings.length > 3 ? <li>+{validationFindings.length - 3} more validation findings</li> : null}
                                </Box>
                              ) : null}
                            </CardContent>
                          </Card>
                        </Box>

                        {decisionTrail.length > 0 ? (
                          <Card variant="outlined" sx={{ mt: 1.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                  Decision trail
                                </Typography>
                                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                  {proposal.decision_trail?.length ?? 0} recorded steps
                                </Typography>
                              </Box>
                              <Box component="ol" sx={{ listStyle: "decimal", pl: 2, mt: 1.5, mb: 0, display: "grid", gap: 1 }}>
                                {decisionTrail.map((event: PolicyProposalEvent, index) => (
                                  <Card
                                    key={`${proposalId}-trail-${event.created_at ?? index}`}
                                    component="li"
                                    variant="outlined"
                                    sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
                                  >
                                    <CardContent sx={{ p: 1.5 }}>
                                      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                        <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                                          {trailEventLabel(event.event)}
                                        </Typography>
                                        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                          {formatTimestamp(event.created_at)}
                                        </Typography>
                                      </Box>
                                      <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                                        {event.actor ?? "unknown"}
                                      </Typography>
                                      {event.note ? (
                                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                          {event.note}
                                        </Typography>
                                      ) : null}
                                    </CardContent>
                                  </Card>
                                ))}
                              </Box>
                            </CardContent>
                          </Card>
                        ) : null}

                        {proposal.provider_set?.length ? (
                          <Card variant="outlined" sx={{ mt: 1.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                  Imported chain preview
                                </Typography>
                                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                  {proposal.provider_set.length} {proposal.provider_set.length === 1 ? "step" : "steps"}
                                </Typography>
                              </Box>
                              <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0, mt: 1.5, display: "grid", gap: 1 }}>
                                {proposal.provider_set.slice(0, 4).map((providerItem) => (
                                  <Card
                                    key={`${proposalId}-provider-set-${providerItem.index}`}
                                    component="li"
                                    variant="outlined"
                                    sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
                                  >
                                    <CardContent sx={{ p: 1.5 }}>
                                      <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                                        Step {providerItem.index + 1}: {providerItem.type}
                                      </Typography>
                                      <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                                        {providerItem.summary}
                                      </Typography>
                                    </CardContent>
                                  </Card>
                                ))}
                                {proposal.provider_set.length > 4 ? (
                                  <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                    +{proposal.provider_set.length - 4} more imported steps
                                  </Typography>
                                ) : null}
                              </Box>
                            </CardContent>
                          </Card>
                        ) : null}

                        {simulationSummary ? (
                          <Card variant="outlined" sx={{ mt: 1.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}>
                            <CardContent sx={{ p: 1.5 }}>
                              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                  Simulation
                                </Typography>
                                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                                  {simulationSummary.allowed ?? 0} allowed · {simulationSummary.denied ?? 0} denied · {simulationSummary.errors ?? 0} errors
                                </Typography>
                              </Box>
                              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                Tested against {simulationSummary.total ?? 0} registry access scenarios.
                              </Typography>
                              {simulationResults.length > 0 ? (
                                <Box component="ul" sx={{ listStyle: "disc", pl: 2, mt: 1, mb: 0, color: "var(--app-muted)", fontSize: 11, display: "grid", gap: 0.5 }}>
                                  {simulationResults.slice(0, 4).map((result, index) => (
                                    <li key={`${proposalId}-simulation-${index}`}>
                                      {result.label || result.resource_id || "Scenario"}: {(result.decision || "unknown").toUpperCase()} ·{" "}
                                      {result.reason || "No reason captured."}
                                    </li>
                                  ))}
                                  {simulationResults.length > 4 ? <li>+{simulationResults.length - 4} more simulated outcomes</li> : null}
                                </Box>
                              ) : null}
                            </CardContent>
                          </Card>
                        ) : null}
                      </Collapse>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </Box>

          {historyProposals.length > 0 ? (
            <Card variant="outlined" sx={{ mt: 2.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
              <CardContent sx={{ p: 2 }}>
                <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                  Recent decisions
                </Typography>
                <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
                  {historyProposals.slice(0, 4).map((proposal) => (
                    <Card
                      key={`history-${proposal.proposal_id ?? "unknown"}`}
                      variant="outlined"
                      sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", boxShadow: "none" }}
                    >
                      <CardContent sx={{ p: 1.5 }}>
                        <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                          <Chip
                            size="small"
                            label={proposalStatusLabel(proposal.status)}
                            sx={{
                              borderRadius: 999,
                              fontSize: 10,
                              fontWeight: 800,
                              textTransform: "uppercase",
                              letterSpacing: "0.12em",
                              height: 22,
                              ...proposalStatusSx(proposal.status),
                            }}
                          />
                          <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                            {actionLabel(proposal.action)}
                          </Typography>
                        </Box>
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          {proposal.description || "No description recorded."}
                        </Typography>
                        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                          {proposal.status === "deployed"
                            ? `Went live ${formatTimestamp(proposal.deployed_at)}`
                            : proposal.status === "rejected"
                              ? `Rejected ${proposal.rejection_reason ? `— ${proposal.rejection_reason}` : ""}`
                              : `Withdrawn ${formatTimestamp(proposal.created_at)}`}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              </CardContent>
            </Card>
          ) : null}
        </CardContent>
      </Card>

      <ConfirmModal
        isOpen={deployModal !== null}
        title="Apply this proposal to the live chain?"
        description={
          deployModal ? `This will deploy the "${actionLabel(deployModal.action)}" proposal to the live policy chain.` : ""
        }
        confirmLabel={requireApproval ? "Approve & apply" : "Apply live"}
        isDangerous={false}
        isLoading={deployModal !== null && busyKey === `approve-${deployModal.proposal_id}`}
        onConfirm={async () => {
          if (!deployModal) return;
          await onApproveAndDeploy(deployModal, proposalNotes[deployModal.proposal_id ?? ""] ?? "", requireApproval, requireSimulation);
          setDeployModal(null);
        }}
        onCancel={() => setDeployModal(null)}
      />

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
        <TextField
          value={proposalNotes[rejectModal ?? ""] ?? ""}
          onChange={(event) =>
            setProposalNotes((current) => ({
              ...current,
              [rejectModal ?? ""]: event.target.value,
            }))
          }
          placeholder="Rejection reason"
          size="small"
          fullWidth
        />
      </ConfirmModal>

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
    </Box>
  );
}

"use client";

import { useState, useCallback, useMemo } from "react";
import type {
  ContractData,
  ContractListResponse,
  ExchangeLogResponse,
  ExchangeLogEntry,
  NegotiateContractResponse,
  ExchangeChainVerifyResponse,
} from "@/lib/registryClient";

async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const payload = (await response.json().catch(() => ({}))) as T & { error?: string };
  if (!response.ok) {
    throw new Error(
      (payload as { error?: string }).error ?? `Request failed (${response.status})`,
    );
  }
  return payload;
}

import { TabBar } from "@/components/security/TabBar";
import { DataTable, type Column } from "@/components/security/DataTable";
import { StatusBadge } from "@/components/security/StatusBadge";
import { TimelineItem } from "@/components/security/TimelineItem";
import { JsonViewer } from "@/components/security/JsonViewer";
import { EmptyState } from "@/components/security/EmptyState";
import { ConfirmationModal } from "@/components/security/ConfirmationModal";

type ActiveTab = "contracts" | "negotiate" | "exchange-log";

interface ContractTerm {
  term_type: string;
  description: string;
  required: boolean;
}

export function ContractsManager({
  initialContracts,
  initialExchangeLog,
}: {
  initialContracts: ContractListResponse | null;
  initialExchangeLog: ExchangeLogResponse | null;
}) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("contracts");
  const [contracts, setContracts] = useState<ContractData[]>(
    initialContracts?.contracts ?? []
  );
  const [exchangeLog, setExchangeLog] = useState<ExchangeLogEntry[]>(
    initialExchangeLog?.entries ?? []
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedContract, setSelectedContract] = useState<ContractData | null>(
    null
  );
  const [expandedContractId, setExpandedContractId] = useState<string | null>(
    null
  );

  // Negotiation form state
  const [negotiationAgentId, setNegotiationAgentId] = useState("");
  const [negotiationTerms, setNegotiationTerms] = useState<ContractTerm[]>([
    { term_type: "", description: "", required: false },
  ]);

  // Modal states
  const [showSignModal, setShowSignModal] = useState(false);
  const [showRevokeModal, setShowRevokeModal] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [verifyingChainId, setVerifyingChainId] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<{
    valid: boolean;
    message: string;
  } | null>(null);

  // Fetch contracts
  const fetchContracts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall<ContractListResponse>("/security/contracts");
      setContracts(data.contracts ?? []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch contracts"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch exchange log
  const fetchExchangeLog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/registry/exchange-log");
      if (!response.ok) throw new Error("Failed to fetch exchange log");
      const data = await response.json();
      if (data) {
        setExchangeLog(data.entries);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch exchange log"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle negotiation
  const handleNegotiate = useCallback(async () => {
    if (!negotiationAgentId.trim()) {
      setError("Agent ID is required");
      return;
    }

    const validTerms = negotiationTerms.filter((t) => t.term_type.trim());
    if (validTerms.length === 0) {
      setError("At least one term is required");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiCall<NegotiateContractResponse>(
        "/security/contracts/negotiate",
        {
          method: "POST",
          body: JSON.stringify({
            agent_id: negotiationAgentId,
            proposed_terms: validTerms,
          }),
        },
      );

      if (response.contract) {
        setContracts((prev) => [response.contract!, ...prev]);
        setNegotiationAgentId("");
        setNegotiationTerms([
          { term_type: "", description: "", required: false },
        ]);
        setActiveTab("contracts");
        setError(null);
      } else {
        setError(response.reason || "Negotiation failed");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to negotiate contract"
      );
    } finally {
      setLoading(false);
    }
  }, [negotiationAgentId, negotiationTerms]);

  // Handle sign contract
  const handleSign = useCallback(async () => {
    if (!selectedContract) return;

    setLoading(true);
    setError(null);
    setShowSignModal(false);

    try {
      await apiCall(`/security/contracts/${encodeURIComponent(selectedContract.contract_id)}/sign`, {
        method: "POST",
        body: JSON.stringify({ agent_id: selectedContract.agent_id }),
      });
      await fetchContracts();
      setSelectedContract(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign contract");
    } finally {
      setLoading(false);
    }
  }, [selectedContract, fetchContracts]);

  // Handle revoke contract
  const handleRevoke = useCallback(async () => {
    if (!selectedContract) return;

    setLoading(true);
    setError(null);
    setShowRevokeModal(false);

    try {
      await apiCall(`/security/contracts/${encodeURIComponent(selectedContract.contract_id)}/revoke`, {
        method: "POST",
        body: JSON.stringify({ reason: revokeReason }),
      });
      await fetchContracts();
      setSelectedContract(null);
      setRevokeReason("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to revoke contract"
      );
    } finally {
      setLoading(false);
    }
  }, [selectedContract, revokeReason, fetchContracts]);

  // Verify chain
  const handleVerifyChain = useCallback(
    async (sessionId: string) => {
      setVerifyingChainId(sessionId);
      setError(null);

      try {
        const result = await apiCall<ExchangeChainVerifyResponse>(
          `/security/contracts/exchange-log/${encodeURIComponent(sessionId)}/verify`,
        );
        if (result.valid) {
          setVerifyResult({
            valid: true,
            message: `Chain verified: ${result.entry_count} entries`,
          });
        } else {
          setVerifyResult({
            valid: false,
            message: "Chain verification failed",
          });
        }
      } catch (err) {
        setVerifyResult({
          valid: false,
          message:
            err instanceof Error ? err.message : "Verification error",
        });
      } finally {
        setVerifyingChainId(null);
      }
    },
    []
  );

  // Add term row
  const addTermRow = useCallback(() => {
    setNegotiationTerms((prev) => [
      ...prev,
      { term_type: "", description: "", required: false },
    ]);
  }, []);

  // Remove term row
  const removeTermRow = useCallback((index: number) => {
    setNegotiationTerms((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Update term
  const updateTerm = useCallback(
    (index: number, field: keyof ContractTerm, value: string | boolean) => {
      setNegotiationTerms((prev) =>
        prev.map((t, i) =>
          i === index
            ? {
                ...t,
                [field]: value,
              }
            : t
        )
      );
    },
    []
  );

  // Contract table columns
  const contractColumns: Column<ContractData>[] = useMemo(
    () => [
      {
        key: "contract_id",
        header: "Contract ID",
        render: (row) => (
          <span className="font-mono text-[10px] text-[--app-muted]">
            {row.contract_id.substring(0, 12)}...
          </span>
        ),
      },
      {
        key: "agent_id",
        header: "Agent ID",
        render: (row) => <span className="text-[11px]">{row.agent_id}</span>,
      },
      {
        key: "status",
        header: "Status",
        render: (row) => <StatusBadge status={row.status} />,
      },
      {
        key: "terms",
        header: "Terms",
        render: (row) => (
          <span className="text-[11px] text-[--app-muted]">
            {row.terms?.length ?? 0} term{(row.terms?.length ?? 0) !== 1 ? "s" : ""}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        render: (row) => (
          <span className="text-[10px] text-[--app-muted]">
            {new Date(row.created_at).toLocaleDateString()}
          </span>
        ),
      },
    ],
    []
  );

  const tabs = [
    { key: "contracts" as const, label: "Active Contracts" },
    { key: "negotiate" as const, label: "Negotiate" },
    { key: "exchange-log" as const, label: "Exchange Log" },
  ];

  // Render tabs
  function renderTabContent() {
    switch (activeTab) {
      case "contracts":
        return (
          <div className="flex flex-col gap-4">
            {contracts.length === 0 ? (
              <EmptyState title="No Contracts" message="Start by negotiating a new contract." />
            ) : (
              <>
                <DataTable
                  data={contracts}
                  columns={contractColumns}
                  onRowClick={(contract) =>
                    setExpandedContractId(
                      expandedContractId === contract.contract_id
                        ? null
                        : contract.contract_id
                    )
                  }
                  pageSize={5}
                />
                {expandedContractId && (
                  <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
                    {contracts.map((contract) => {
                      if (contract.contract_id !== expandedContractId)
                        return null;
                      return (
                        <div key={contract.contract_id} className="space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                              Contract Details
                            </h3>
                            <button
                              onClick={() => setExpandedContractId(null)}
                              className="text-[11px] text-[--app-muted] hover:text-[--app-fg]"
                            >
                              ✕
                            </button>
                          </div>

                          <div className="space-y-2">
                            <div className="text-[10px]">
                              <span className="text-[--app-muted]">ID:</span>
                              <span className="ml-2 font-mono text-[--app-fg]">
                                {contract.contract_id}
                              </span>
                            </div>
                            <div className="text-[10px]">
                              <span className="text-[--app-muted]">Server:</span>
                              <span className="ml-2 text-[--app-fg]">
                                {contract.server_id}
                              </span>
                            </div>
                            <div className="text-[10px]">
                              <span className="text-[--app-muted]">Agent:</span>
                              <span className="ml-2 text-[--app-fg]">
                                {contract.agent_id}
                              </span>
                            </div>
                            {contract.expires_at && (
                              <div className="text-[10px]">
                                <span className="text-[--app-muted]">
                                  Expires:
                                </span>
                                <span className="ml-2 text-[--app-fg]">
                                  {new Date(
                                    contract.expires_at
                                  ).toLocaleDateString()}
                                </span>
                              </div>
                            )}
                          </div>

                          <div className="space-y-2 border-t border-[--app-border] pt-2">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-[--app-muted]">
                              Terms ({contract.terms?.length ?? 0})
                            </p>
                            {contract.terms && contract.terms.length > 0 ? (
                              <div className="space-y-1">
                                {contract.terms.map((term, idx) => (
                                  <div
                                    key={idx}
                                    className="rounded bg-[--app-control-bg] p-2 text-[10px]"
                                  >
                                    <div className="font-mono text-[--app-muted]">
                                      {term.term_type}
                                    </div>
                                    <div className="mt-0.5 text-[--app-muted]">
                                      {term.description}
                                    </div>
                                    {term.required && (
                                      <div className="mt-0.5 text-amber-300">
                                        Required
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-[10px] text-[--app-muted]">
                                No terms
                              </p>
                            )}
                          </div>

                          {contract.signatures &&
                            Object.keys(contract.signatures).length > 0 && (
                              <div className="space-y-2 border-t border-[--app-border] pt-2">
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-[--app-muted]">
                                  Signatures
                                </p>
                                <JsonViewer
                                  data={contract.signatures}
                                />
                              </div>
                            )}

                          <div className="flex gap-2 border-t border-[--app-border] pt-3">
                            {contract.status !== "signed" && (
                              <button
                                onClick={() => {
                                  setSelectedContract(contract);
                                  setShowSignModal(true);
                                }}
                                disabled={loading}
                                className="rounded-full bg-[--app-accent] px-3 py-1.5 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
                              >
                                Sign
                              </button>
                            )}
                            {contract.status !== "revoked" && (
                              <button
                                onClick={() => {
                                  setSelectedContract(contract);
                                  setShowRevokeModal(true);
                                }}
                                disabled={loading}
                                className="rounded-full border border-red-700/60 px-3 py-1 text-[11px] font-medium text-red-200 hover:bg-red-900/50 transition disabled:opacity-50"
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        );

      case "negotiate":
        return (
          <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
            <div className="space-y-4">
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                  Agent ID
                </label>
                <input
                  type="text"
                  value={negotiationAgentId}
                  onChange={(e) => setNegotiationAgentId(e.target.value)}
                  placeholder="e.g., agent-xyz-123"
                  disabled={loading}
                  className="mt-1.5 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none disabled:opacity-50"
                />
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                    Terms
                  </label>
                  <button
                    onClick={addTermRow}
                    disabled={loading}
                    className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg] disabled:opacity-50"
                  >
                    + Add Term
                  </button>
                </div>

                <div className="space-y-2">
                  {negotiationTerms.map((term, idx) => (
                    <div
                      key={idx}
                      className="space-y-2 rounded-xl border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]"
                    >
                      <div className="flex gap-2 items-end">
                        <div className="flex-1">
                          <label className="text-[10px] text-[--app-muted]">
                            Type
                          </label>
                          <input
                            type="text"
                            value={term.term_type}
                            onChange={(e) =>
                              updateTerm(idx, "term_type", e.target.value)
                            }
                            placeholder="e.g., rate_limit"
                            disabled={loading}
                            className="mt-1 w-full rounded-lg bg-[--app-chrome-bg] px-2 py-1.5 text-[11px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none disabled:opacity-50"
                          />
                        </div>
                        {negotiationTerms.length > 1 && (
                          <button
                            onClick={() => removeTermRow(idx)}
                            disabled={loading}
                            className="rounded-lg border border-red-700/40 px-2 py-1.5 text-[11px] text-red-300/70 hover:bg-red-900/20 disabled:opacity-50"
                          >
                            Remove
                          </button>
                        )}
                      </div>

                      <div>
                        <label className="text-[10px] text-[--app-muted]">
                          Description
                        </label>
                        <input
                          type="text"
                          value={term.description}
                          onChange={(e) =>
                            updateTerm(idx, "description", e.target.value)
                          }
                          placeholder="What does this term require?"
                          disabled={loading}
                          className="mt-1 w-full rounded-lg bg-[--app-chrome-bg] px-2 py-1.5 text-[11px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none disabled:opacity-50"
                        />
                      </div>

                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={term.required}
                          onChange={(e) =>
                            updateTerm(idx, "required", e.target.checked)
                          }
                          disabled={loading}
                          className="h-3 w-3 rounded border-[--app-border] bg-[--app-chrome-bg] text-[--app-accent] disabled:opacity-50"
                        />
                        <span className="text-[10px] text-[--app-muted]">
                          Required
                        </span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {error && (
                <div className="rounded-lg bg-red-500/10 px-3 py-2 text-[11px] text-red-300 border border-red-700/30">
                  {error}
                </div>
              )}

              <button
                onClick={handleNegotiate}
                disabled={loading || !negotiationAgentId.trim()}
                className="mt-2 w-full rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
              >
                {loading ? "Negotiating..." : "Negotiate Contract"}
              </button>
            </div>
          </div>
        );

      case "exchange-log":
        return (
          <div className="space-y-4">
            {exchangeLog.length === 0 ? (
              <EmptyState title="No Exchange Log" message="No exchange log entries found." />
            ) : (
              <div className="space-y-2">
                {exchangeLog.map((entry, idx) => (
                  <div key={idx}>
                    <TimelineItem
                      title={entry.message_type}
                      timestamp={new Date(entry.timestamp).toLocaleString()}
                      detail={`Direction: ${entry.direction}${entry.session_id ? ` | Session: ${entry.session_id.substring(0, 16)}...` : ""}${entry.hash ? ` | Hash: ${entry.hash.substring(0, 16)}...` : ""}`}
                      status={entry.direction === "inbound" ? "received" : "sent"}
                    />
                    {entry.payload && (
                      <div className="ml-8 mt-2">
                        <JsonViewer data={entry.payload} />
                      </div>
                    )}
                    {entry.session_id && (
                      <button
                        onClick={() => handleVerifyChain(entry.session_id)}
                        disabled={
                          loading || verifyingChainId === entry.session_id
                        }
                        className="ml-8 mt-2 text-[10px] font-medium text-[--app-muted] hover:text-[--app-fg] disabled:opacity-50"
                      >
                        {verifyingChainId === entry.session_id
                          ? "Verifying..."
                          : "Verify Chain"}
                      </button>
                    )}
                  </div>
                ))}

                {verifyResult && (
                  <div
                    className={`rounded-lg px-3 py-2 text-[11px] border ${
                      verifyResult.valid
                        ? "bg-[--app-control-active-bg] text-[--app-fg] border-[--app-border]"
                        : "bg-red-500/10 text-red-300 border-red-700/30"
                    }`}
                  >
                    {verifyResult.message}
                  </div>
                )}
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && activeTab !== "negotiate" && (
        <div className="rounded-lg bg-red-500/10 px-4 py-3 text-[11px] text-red-300 border border-red-700/30">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-200/70 hover:text-red-200"
          >
            ✕
          </button>
        </div>
      )}

      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={(key) => setActiveTab(key as ActiveTab)} />

      {renderTabContent()}

      {showSignModal && selectedContract && (
        <ConfirmationModal
          open={showSignModal}
          title="Sign Contract"
          message={`Sign contract ${selectedContract.contract_id.substring(0, 12)}...?`}
          confirmLabel="Sign"
          cancelLabel="Cancel"
          onConfirm={handleSign}
          onCancel={() => {
            setShowSignModal(false);
            setSelectedContract(null);
          }}
        />
      )}

      {showRevokeModal && selectedContract && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="max-w-sm space-y-4 rounded-3xl border border-[--app-border] bg-[--app-chrome-bg] p-6 ring-1 ring-[--app-surface-ring]">
            <h2 className="text-[12px] font-semibold uppercase tracking-[0.18em] text-[--app-fg]">
              Revoke Contract
            </h2>
            <p className="text-[11px] text-[--app-muted]">
              Are you sure you want to revoke this contract? This action cannot
              be undone.
            </p>
            <input
              type="text"
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              placeholder="Reason for revocation (optional)"
              disabled={loading}
              className="w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none disabled:opacity-50"
            />
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleRevoke}
                disabled={loading}
                className="flex-1 rounded-full bg-red-600/80 px-3 py-1.5 text-[11px] font-semibold text-red-50 hover:bg-red-600 transition disabled:opacity-50"
              >
                {loading ? "Revoking..." : "Revoke"}
              </button>
              <button
                onClick={() => {
                  setShowRevokeModal(false);
                  setSelectedContract(null);
                  setRevokeReason("");
                }}
                disabled={loading}
                className="flex-1 rounded-full border border-[--app-border] px-3 py-1 text-[11px] font-medium text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

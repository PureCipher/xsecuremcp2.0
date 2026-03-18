"use client";

import { useState, useCallback, useMemo } from "react";
import type {
  ContractData,
  ContractListResponse,
  ExchangeLogResponse,
  ExchangeLogEntry,
  NegotiateContractResponse,
} from "@/lib/registryClient";
import {
  listContracts,
  negotiateContract,
  getContractDetails,
  signContract,
  revokeContract,
  verifyExchangeChain,
} from "@/lib/registryClient";

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
      const data = await listContracts();
      if (data) {
        setContracts(data.contracts);
      }
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
      const response = (await negotiateContract({
        agent_id: negotiationAgentId,
        terms: validTerms,
      })) as NegotiateContractResponse | null;

      if (response?.contract) {
        setContracts((prev) => [response.contract!, ...prev]);
        setNegotiationAgentId("");
        setNegotiationTerms([
          { term_type: "", description: "", required: false },
        ]);
        setActiveTab("contracts");
        setError(null);
      } else {
        setError(response?.reason || "Negotiation failed");
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
      await signContract(selectedContract.contract_id, {
        agent_id: selectedContract.agent_id,
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
      await revokeContract(selectedContract.contract_id, revokeReason);
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
        const result = await verifyExchangeChain(sessionId);
        if (result?.valid) {
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
          <span className="font-mono text-[10px] text-emerald-200">
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
          <span className="text-[11px] text-emerald-200">
            {row.terms?.length ?? 0} term{(row.terms?.length ?? 0) !== 1 ? "s" : ""}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        render: (row) => (
          <span className="text-[10px] text-emerald-300/70">
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
                  <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
                    {contracts.map((contract) => {
                      if (contract.contract_id !== expandedContractId)
                        return null;
                      return (
                        <div key={contract.contract_id} className="space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                              Contract Details
                            </h3>
                            <button
                              onClick={() => setExpandedContractId(null)}
                              className="text-[11px] text-emerald-300/60 hover:text-emerald-200"
                            >
                              ✕
                            </button>
                          </div>

                          <div className="space-y-2">
                            <div className="text-[10px]">
                              <span className="text-emerald-400">ID:</span>
                              <span className="ml-2 font-mono text-emerald-200">
                                {contract.contract_id}
                              </span>
                            </div>
                            <div className="text-[10px]">
                              <span className="text-emerald-400">Server:</span>
                              <span className="ml-2 text-emerald-200">
                                {contract.server_id}
                              </span>
                            </div>
                            <div className="text-[10px]">
                              <span className="text-emerald-400">Agent:</span>
                              <span className="ml-2 text-emerald-200">
                                {contract.agent_id}
                              </span>
                            </div>
                            {contract.expires_at && (
                              <div className="text-[10px]">
                                <span className="text-emerald-400">
                                  Expires:
                                </span>
                                <span className="ml-2 text-emerald-200">
                                  {new Date(
                                    contract.expires_at
                                  ).toLocaleDateString()}
                                </span>
                              </div>
                            )}
                          </div>

                          <div className="space-y-2 border-t border-emerald-700/40 pt-2">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                              Terms ({contract.terms?.length ?? 0})
                            </p>
                            {contract.terms && contract.terms.length > 0 ? (
                              <div className="space-y-1">
                                {contract.terms.map((term, idx) => (
                                  <div
                                    key={idx}
                                    className="rounded bg-emerald-950/50 p-2 text-[10px]"
                                  >
                                    <div className="font-mono text-emerald-300">
                                      {term.term_type}
                                    </div>
                                    <div className="mt-0.5 text-emerald-200/80">
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
                              <p className="text-[10px] text-emerald-300/50">
                                No terms
                              </p>
                            )}
                          </div>

                          {contract.signatures &&
                            Object.keys(contract.signatures).length > 0 && (
                              <div className="space-y-2 border-t border-emerald-700/40 pt-2">
                                <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                                  Signatures
                                </p>
                                <JsonViewer
                                  data={contract.signatures}
                                />
                              </div>
                            )}

                          <div className="flex gap-2 border-t border-emerald-700/40 pt-3">
                            {contract.status !== "signed" && (
                              <button
                                onClick={() => {
                                  setSelectedContract(contract);
                                  setShowSignModal(true);
                                }}
                                disabled={loading}
                                className="rounded-full bg-emerald-600/80 px-3 py-1.5 text-[11px] font-semibold text-emerald-50 hover:bg-emerald-600 transition disabled:opacity-50"
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
          <div className="rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
            <div className="space-y-4">
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                  Agent ID
                </label>
                <input
                  type="text"
                  value={negotiationAgentId}
                  onChange={(e) => setNegotiationAgentId(e.target.value)}
                  placeholder="e.g., agent-xyz-123"
                  disabled={loading}
                  className="mt-1.5 w-full rounded-xl bg-emerald-950/80 px-3 py-2 text-[12px] text-emerald-100 ring-1 ring-emerald-700/50 focus:ring-emerald-500 focus:outline-none disabled:opacity-50"
                />
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                    Terms
                  </label>
                  <button
                    onClick={addTermRow}
                    disabled={loading}
                    className="text-[11px] font-medium text-emerald-300 hover:text-emerald-200 disabled:opacity-50"
                  >
                    + Add Term
                  </button>
                </div>

                <div className="space-y-2">
                  {negotiationTerms.map((term, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl bg-emerald-950/50 p-3 space-y-2"
                    >
                      <div className="flex gap-2 items-end">
                        <div className="flex-1">
                          <label className="text-[10px] text-emerald-300/70">
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
                            className="mt-1 w-full rounded-lg bg-emerald-950/80 px-2 py-1.5 text-[11px] text-emerald-100 ring-1 ring-emerald-700/50 focus:ring-emerald-500 focus:outline-none disabled:opacity-50"
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
                        <label className="text-[10px] text-emerald-300/70">
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
                          className="mt-1 w-full rounded-lg bg-emerald-950/80 px-2 py-1.5 text-[11px] text-emerald-100 ring-1 ring-emerald-700/50 focus:ring-emerald-500 focus:outline-none disabled:opacity-50"
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
                          className="h-3 w-3 rounded border-emerald-700 bg-emerald-950 text-emerald-500 disabled:opacity-50"
                        />
                        <span className="text-[10px] text-emerald-200">
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
                className="mt-2 w-full rounded-full bg-emerald-600/80 px-4 py-2 text-[11px] font-semibold text-emerald-50 hover:bg-emerald-600 transition disabled:opacity-50"
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
                        className="ml-8 mt-2 text-[10px] font-medium text-emerald-300 hover:text-emerald-200 disabled:opacity-50"
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
                        ? "bg-emerald-500/10 text-emerald-300 border-emerald-700/30"
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
          <div className="rounded-3xl bg-emerald-900/80 p-6 ring-1 ring-emerald-700/60 max-w-sm space-y-4">
            <h2 className="text-[12px] font-semibold uppercase tracking-[0.18em] text-emerald-50">
              Revoke Contract
            </h2>
            <p className="text-[11px] text-emerald-200/80">
              Are you sure you want to revoke this contract? This action cannot
              be undone.
            </p>
            <input
              type="text"
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              placeholder="Reason for revocation (optional)"
              disabled={loading}
              className="w-full rounded-xl bg-emerald-950/80 px-3 py-2 text-[12px] text-emerald-100 ring-1 ring-emerald-700/50 focus:ring-emerald-500 focus:outline-none disabled:opacity-50"
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
                className="flex-1 rounded-full border border-emerald-700/60 px-3 py-1 text-[11px] font-medium text-emerald-200 hover:bg-emerald-900/50 transition disabled:opacity-50"
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

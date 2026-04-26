"use client";

import { useState, useCallback, useMemo } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  TextField,
  Typography,
} from "@mui/material";
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
          <Box
            component="span"
            sx={{
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 11,
              color: "var(--app-muted)",
            }}
          >
            {row.contract_id.substring(0, 12)}...
          </Box>
        ),
      },
      {
        key: "agent_id",
        header: "Agent ID",
        render: (row) => (
          <Typography component="span" sx={{ fontSize: 12 }}>
            {row.agent_id}
          </Typography>
        ),
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
          <Typography component="span" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
            {row.terms?.length ?? 0} term{(row.terms?.length ?? 0) !== 1 ? "s" : ""}
          </Typography>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        render: (row) => (
          <Typography component="span" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            {new Date(row.created_at).toLocaleDateString()}
          </Typography>
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
  const signedCount = contracts.filter((contract) => contract.status === "signed").length;

  // Render tabs
  function renderTabContent() {
    switch (activeTab) {
      case "contracts":
        return (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
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
                  <Card variant="outlined">
                    {contracts.map((contract) => {
                      if (contract.contract_id !== expandedContractId)
                        return null;
                      return (
                        <CardContent key={contract.contract_id} sx={{ p: 2.5, display: "grid", gap: 2 }}>
                          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                            <Typography sx={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.02em", color: "var(--app-fg)" }}>
                              Contract Details
                            </Typography>
                            <Button size="small" variant="text" onClick={() => setExpandedContractId(null)} sx={{ color: "var(--app-muted)" }}>
                              Close
                            </Button>
                          </Box>

                          <Box sx={{ display: "grid", gap: 1 }}>
                            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                              ID:{" "}
                              <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-fg)" }}>
                                {contract.contract_id}
                              </Box>
                            </Typography>
                            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                              Server: <Box component="span" sx={{ color: "var(--app-fg)" }}>{contract.server_id}</Box>
                            </Typography>
                            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                              Agent: <Box component="span" sx={{ color: "var(--app-fg)" }}>{contract.agent_id}</Box>
                            </Typography>
                            {contract.expires_at ? (
                              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                                Expires:{" "}
                                <Box component="span" sx={{ color: "var(--app-fg)" }}>
                                  {new Date(contract.expires_at).toLocaleDateString()}
                                </Box>
                              </Typography>
                            ) : null}
                          </Box>

                          <Divider sx={{ borderColor: "var(--app-border)" }} />

                          <Box>
                            <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                              Terms ({contract.terms?.length ?? 0})
                            </Typography>
                            {contract.terms && contract.terms.length > 0 ? (
                              <Box sx={{ mt: 1, display: "grid", gap: 1 }}>
                                {contract.terms.map((term, idx) => (
                                  <Card
                                    key={idx}
                                    variant="outlined"
                                    sx={{ bgcolor: "var(--app-control-bg)" }}
                                  >
                                    <CardContent sx={{ p: 1.5 }}>
                                      <Typography sx={{ fontSize: 12, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-muted)" }}>
                                        {term.term_type}
                                      </Typography>
                                      <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                                        {term.description}
                                      </Typography>
                                      {term.required ? (
                                        <Chip size="small" label="Required" sx={{ mt: 1, bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e", fontWeight: 700, fontSize: 11 }} />
                                      ) : null}
                                    </CardContent>
                                  </Card>
                                ))}
                              </Box>
                            ) : (
                              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>No terms</Typography>
                            )}
                          </Box>

                          {contract.signatures && Object.keys(contract.signatures).length > 0 ? (
                            <>
                              <Divider sx={{ borderColor: "var(--app-border)" }} />
                              <Box>
                                <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                                  Signatures
                                </Typography>
                                <Box sx={{ mt: 1 }}>
                                  <JsonViewer data={contract.signatures} />
                                </Box>
                              </Box>
                            </>
                          ) : null}

                          <Divider sx={{ borderColor: "var(--app-border)" }} />

                          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                            {contract.status !== "signed" ? (
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => {
                                  setSelectedContract(contract);
                                  setShowSignModal(true);
                                }}
                                disabled={loading}
                                sx={{ bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" } }}
                              >
                                Sign
                              </Button>
                            ) : null}
                            {contract.status !== "revoked" ? (
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={() => {
                                  setSelectedContract(contract);
                                  setShowRevokeModal(true);
                                }}
                                disabled={loading}
                                sx={{ borderColor: "rgba(239, 68, 68, 0.45)", color: "#b91c1c", "&:hover": { bgcolor: "rgba(239, 68, 68, 0.08)", borderColor: "#ef4444" } }}
                              >
                                Revoke
                              </Button>
                            ) : null}
                          </Box>
                        </CardContent>
                      );
                    })}
                  </Card>
                )}
              </>
            )}
          </Box>
        );

      case "negotiate":
        return (
          <Card variant="outlined">
            <CardContent sx={{ p: 3, display: "grid", gap: 2.5 }}>
              <Box>
                <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                  Agent ID
                </Typography>
                <Box sx={{ mt: 1.25 }}>
                  {/* Keep MUI feel; avoid Stack typing issues */}
                  <Box
                    component="input"
                    value={negotiationAgentId}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNegotiationAgentId(e.target.value)}
                    placeholder="e.g., agent-xyz-123"
                    disabled={loading}
                    sx={{
                      width: "100%",
                      borderRadius: 2,
                      bgcolor: "var(--app-control-bg)",
                      px: 1.5,
                      py: 1.25,
                      fontSize: 14,
                      color: "var(--app-fg)",
                      border: "1px solid var(--app-border)",
                      outline: "none",
                      "&:focus": { borderColor: "var(--app-accent)", boxShadow: "0 0 0 3px var(--app-control-active-bg)" },
                      "&:disabled": { opacity: 0.6 },
                    }}
                  />
                </Box>
              </Box>

              <Box>
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Terms
                  </Typography>
                  <Button size="small" variant="text" onClick={addTermRow} disabled={loading} sx={{ color: "var(--app-muted)" }}>
                    Add term
                  </Button>
                </Box>

                <Box sx={{ mt: 1.5, display: "grid", gap: 1.5 }}>
                  {negotiationTerms.map((term, idx) => (
                    <Card key={idx} variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                      <CardContent sx={{ p: 2, display: "grid", gap: 1.5 }}>
                        <Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-end" }}>
                          <Box sx={{ flex: 1 }}>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>Type</Typography>
                            <Box
                              component="input"
                              value={term.term_type}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                updateTerm(idx, "term_type", e.target.value)
                              }
                              placeholder="e.g., rate_limit"
                              disabled={loading}
                              sx={{
                                mt: 1,
                                width: "100%",
                                borderRadius: 2,
                                bgcolor: "var(--app-control-bg)",
                                px: 1.25,
                                py: 1,
                                fontSize: 13,
                                color: "var(--app-fg)",
                                border: "1px solid var(--app-border)",
                                outline: "none",
                                "&:focus": { borderColor: "var(--app-accent)", boxShadow: "0 0 0 3px var(--app-control-active-bg)" },
                                "&:disabled": { opacity: 0.6 },
                              }}
                            />
                          </Box>

                          {negotiationTerms.length > 1 ? (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => removeTermRow(idx)}
                              disabled={loading}
                              sx={{
                                borderRadius: 2,
                                borderColor: "rgba(239, 68, 68, 0.4)",
                                color: "#b91c1c",
                                "&:hover": { bgcolor: "rgba(239, 68, 68, 0.08)", borderColor: "#ef4444" },
                              }}
                            >
                              Remove
                            </Button>
                          ) : null}
                        </Box>

                        <Box>
                          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>Description</Typography>
                          <Box
                            component="input"
                            value={term.description}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              updateTerm(idx, "description", e.target.value)
                            }
                            placeholder="What does this term require?"
                            disabled={loading}
                            sx={{
                              mt: 1,
                              width: "100%",
                              borderRadius: 2,
                              bgcolor: "var(--app-control-bg)",
                              px: 1.25,
                              py: 1,
                              fontSize: 13,
                              color: "var(--app-fg)",
                              border: "1px solid var(--app-border)",
                              outline: "none",
                              "&:focus": { borderColor: "var(--app-accent)", boxShadow: "0 0 0 3px var(--app-control-active-bg)" },
                              "&:disabled": { opacity: 0.6 },
                            }}
                          />
                        </Box>

                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <Box
                            component="input"
                            type="checkbox"
                            checked={term.required}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              updateTerm(idx, "required", e.target.checked)
                            }
                            disabled={loading}
                            sx={{
                              width: 16,
                              height: 16,
                              accentColor: "var(--app-accent)",
                              "&:disabled": { opacity: 0.6 },
                            }}
                          />
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            Required
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              </Box>

              {error ? (
                <Card
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    borderColor: "rgba(239, 68, 68, 0.35)",
                    bgcolor: "rgba(239, 68, 68, 0.10)",
                  }}
                >
                  <CardContent sx={{ py: 1.25, px: 1.5 }}>
                    <Typography sx={{ fontSize: 13, color: "#b91c1c" }}>
                      {error}
                    </Typography>
                  </CardContent>
                </Card>
              ) : null}

              <Button
                onClick={handleNegotiate}
                disabled={loading || !negotiationAgentId.trim()}
                variant="contained"
                sx={{
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  py: 1.25,
                  fontWeight: 800,
                  "&:hover": { bgcolor: "var(--app-accent)" },
                }}
              >
                {loading ? "Negotiating..." : "Negotiate Contract"}
              </Button>
            </CardContent>
          </Card>
        );

      case "exchange-log":
        return (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {exchangeLog.length === 0 ? (
              <EmptyState title="No Exchange Log" message="No exchange log entries found." />
            ) : (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                {exchangeLog.map((entry, idx) => (
                  <Box key={idx}>
                    <TimelineItem
                      title={entry.message_type}
                      timestamp={new Date(entry.timestamp).toLocaleString()}
                      detail={`Direction: ${entry.direction}${entry.session_id ? ` | Session: ${entry.session_id.substring(0, 16)}...` : ""}${entry.hash ? ` | Hash: ${entry.hash.substring(0, 16)}...` : ""}`}
                      status={entry.direction === "inbound" ? "received" : "sent"}
                    />
                    {entry.payload && (
                      <Box sx={{ ml: 4, mt: 1.5 }}>
                        <JsonViewer data={entry.payload} />
                      </Box>
                    )}
                    {entry.session_id && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => handleVerifyChain(entry.session_id)}
                        disabled={
                          loading || verifyingChainId === entry.session_id
                        }
                        sx={{
                          mt: 1.25,
                          ml: 4,
                          alignSelf: "flex-start",
                          color: "var(--app-muted)",
                          fontWeight: 700,
                          "&:hover": { color: "var(--app-fg)" },
                        }}
                      >
                        {verifyingChainId === entry.session_id
                          ? "Verifying..."
                          : "Verify Chain"}
                      </Button>
                    )}
                  </Box>
                ))}

                {verifyResult && (
                  <Card
                    variant="outlined"
                    sx={{
                      borderRadius: 2,
                      borderColor: verifyResult.valid
                        ? "var(--app-border)"
                        : "rgba(239, 68, 68, 0.35)",
                      bgcolor: verifyResult.valid
                        ? "var(--app-control-active-bg)"
                        : "rgba(239, 68, 68, 0.10)",
                    }}
                  >
                    <CardContent sx={{ py: 1.25, px: 1.5 }}>
                      <Typography
                        sx={{
                          fontSize: 13,
                          color: verifyResult.valid
                            ? "var(--app-fg)"
                            : "rgb(252, 165, 165)",
                        }}
                      >
                        {verifyResult.message}
                      </Typography>
                    </CardContent>
                  </Card>
                )}
              </Box>
            )}
          </Box>
        );

      default:
        return null;
    }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
      {error && activeTab !== "negotiate" ? (
        <Card
          variant="outlined"
          sx={{
            borderRadius: 2,
            borderColor: "rgba(239, 68, 68, 0.35)",
            bgcolor: "rgba(239, 68, 68, 0.10)",
          }}
        >
          <CardContent sx={{ py: 1.25, px: 1.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Typography sx={{ fontSize: 13, color: "rgb(252, 165, 165)" }}>
              {error}
            </Typography>
            <Button size="small" variant="text" onClick={() => setError(null)} sx={{ color: "rgba(254, 202, 202, 0.8)" }}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Card variant="outlined" sx={{ overflow: "hidden" }}>
        <CardContent sx={{ p: 0 }}>
          <Box
            sx={{
              p: { xs: 2.5, md: 3 },
              display: "flex",
              flexDirection: { xs: "column", md: "row" },
              alignItems: { xs: "flex-start", md: "center" },
              justifyContent: "space-between",
              gap: 2,
            }}
          >
            <Box sx={{ display: "grid", gap: 0.75, maxWidth: 720 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Contract workspace
              </Typography>
              <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
                Negotiate and verify agent agreements
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Manage active contracts, negotiate terms, and verify exchange logs from one broker workflow.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Chip label={`${contracts.length} contracts`} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
              <Chip label={`${signedCount} signed`} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700 }} />
              <Chip label={`${exchangeLog.length} log entries`} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
            </Box>
          </Box>

          <Divider />
          <Box sx={{ px: { xs: 1.5, md: 2 }, bgcolor: "var(--app-control-bg)" }}>
            <TabBar tabs={tabs} activeTab={activeTab} onTabChange={(key) => setActiveTab(key as ActiveTab)} />
          </Box>
          <Divider />

          <Box sx={{ p: { xs: 2, md: 2.5 } }}>
            {contracts.length === 0 && activeTab === "contracts" ? (
              <Box
                sx={{
                  p: { xs: 2.5, md: 3 },
                  borderRadius: 3,
                  border: "1px solid var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  display: "grid",
                  gap: 1.5,
                }}
              >
                <Chip
                  label="Contract negotiation ready"
                  size="small"
                  sx={{ justifySelf: "start", bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)" }}
                />
                <Typography sx={{ fontSize: 15, fontWeight: 700, color: "var(--app-fg)" }}>
                  Start by negotiating a real contract.
                </Typography>
                <Typography sx={{ maxWidth: 700, fontSize: 13, color: "var(--app-muted)" }}>
                  Contracts will appear here after you negotiate terms with an agent and sign the agreement.
                  Signed and revoked states remain available for audit.
                </Typography>
                <Button
                  type="button"
                  variant="contained"
                  onClick={() => setActiveTab("negotiate")}
                  sx={{ justifySelf: "start" }}
                >
                  Negotiate contract
                </Button>
              </Box>
            ) : (
              renderTabContent()
            )}
          </Box>
        </CardContent>
      </Card>

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
        <Dialog
          open={showRevokeModal}
          onClose={() => {
            if (loading) return;
            setShowRevokeModal(false);
            setSelectedContract(null);
            setRevokeReason("");
          }}
          fullWidth
          maxWidth="sm"
          slotProps={{
            paper: {
              sx: {
                borderRadius: 4,
                bgcolor: "var(--app-chrome-bg)",
                border: "1px solid var(--app-border)",
                backgroundImage: "none",
              },
            },
          }}
        >
          <DialogTitle sx={{ color: "var(--app-fg)", fontWeight: 800 }}>
            Revoke Contract
          </DialogTitle>
          <DialogContent sx={{ pt: 1 }}>
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Are you sure you want to revoke this contract? This action cannot be undone.
            </Typography>
            <Box sx={{ mt: 2 }}>
              <TextField
                fullWidth
                size="small"
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                placeholder="Reason for revocation (optional)"
                disabled={loading}
              />
            </Box>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button
              onClick={() => {
                if (loading) return;
                setShowRevokeModal(false);
                setSelectedContract(null);
                setRevokeReason("");
              }}
              variant="outlined"
              disabled={loading}
              sx={{
                borderColor: "var(--app-border)",
                color: "var(--app-muted)",
                "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRevoke}
              variant="contained"
              disabled={loading}
              sx={{
                bgcolor: "rgba(239, 68, 68, 0.85)",
                color: "#fff",
                "&:hover": { bgcolor: "rgb(220, 38, 38)" },
              }}
            >
              {loading ? "Revoking..." : "Revoke"}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
}

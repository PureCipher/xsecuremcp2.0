"use client";

import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  TextField,
  Typography,
} from "@mui/material";
import type {
  JurisdictionListResponse,
  InstitutionListResponse,
  ConsentEvaluationResponse,
  ConsentAccessRights,
  JurisdictionPolicy,
} from "@/lib/registryClient";
import {
  StatusBadge,
  MetricCard,
  KeyValuePanel,
  TabBar,
  DataTable,
} from "@/components/security";
import type { Column } from "@/components/security";

type TabKey = "evaluate" | "access-rights" | "jurisdictions" | "graph";

export function ConsentManager({
  initialJurisdictions,
  initialInstitutions,
}: {
  initialJurisdictions: JurisdictionListResponse | null;
  initialInstitutions: InstitutionListResponse | null;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("evaluate");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Evaluate tab state
  const [evaluateSourceId, setEvaluateSourceId] = useState("");
  const [evaluateTargetId, setEvaluateTargetId] = useState("");
  const [evaluateScope, setEvaluateScope] = useState("");
  const [evaluateSourceJurisdiction, setEvaluateSourceJurisdiction] = useState("");
  const [evaluateTargetJurisdiction, setEvaluateTargetJurisdiction] = useState("");
  const [evaluateJurisdictions, setEvaluateJurisdictions] = useState("");
  const [evaluateRequireAll, setEvaluateRequireAll] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState<ConsentEvaluationResponse | null>(null);

  // Access rights tab state
  const [accessRightsAgentId, setAccessRightsAgentId] = useState("");
  const [accessRightsResourceId, setAccessRightsResourceId] = useState("");
  const [accessRightsResult, setAccessRightsResult] = useState<ConsentAccessRights | null>(null);

  // Expanded jurisdiction row
  const [expandedJurisdiction, setExpandedJurisdiction] = useState<string | null>(null);

  const jurisdictions = initialJurisdictions?.jurisdictions ?? {};
  const institutions = initialInstitutions?.institutions ?? {};

  // Convert jurisdictions and institutions to array format
  const jurisdictionsList = Object.entries(jurisdictions).map(([id, policy]) => ({
    id,
    ...policy,
  }));

  const institutionsList = Object.entries(institutions).map(([id, data]) => ({
    id,
    ...data,
  }));

  async function handleEvaluate() {
    setLoading(true);
    setError(null);
    setEvaluationResult(null);

    try {
      const body: Record<string, unknown> = {
        source_id: evaluateSourceId,
        target_id: evaluateTargetId,
        scope: evaluateScope,
        geographic_context: {
          source_jurisdiction: evaluateSourceJurisdiction,
          target_jurisdiction: evaluateTargetJurisdiction,
        },
      };

      if (evaluateJurisdictions.trim()) {
        body.jurisdictions = evaluateJurisdictions
          .split(",")
          .map((j) => j.trim())
          .filter(Boolean);
      }

      if (evaluateRequireAll) {
        body.require_all_jurisdictions = true;
      }

      const res = await fetch("/api/security-proxy/consent/federated/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data = await res.json();
      setEvaluationResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate consent");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccessRightsLookup() {
    setLoading(true);
    setError(null);
    setAccessRightsResult(null);

    try {
      const res = await fetch(
        `/api/security-proxy/consent/federated/access-rights/${encodeURIComponent(accessRightsAgentId)}/${encodeURIComponent(accessRightsResourceId)}`,
        { method: "GET" }
      );

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data = await res.json();
      setAccessRightsResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch access rights");
    } finally {
      setLoading(false);
    }
  }

  const tabs = [
    { key: "evaluate", label: "Evaluate" },
    { key: "access-rights", label: "Access Rights" },
    { key: "jurisdictions", label: "Jurisdictions" },
    { key: "graph", label: "Graph Explorer" },
  ];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={(key) => setActiveTab(key as TabKey)} />

      {error ? <Alert severity="error">{error}</Alert> : null}

      {/* Evaluate Tab */}
      {activeTab === "evaluate" && (
        <EvaluateTab
          sourceId={evaluateSourceId}
          setSourceId={setEvaluateSourceId}
          targetId={evaluateTargetId}
          setTargetId={setEvaluateTargetId}
          scope={evaluateScope}
          setScope={setEvaluateScope}
          sourceJurisdiction={evaluateSourceJurisdiction}
          setSourceJurisdiction={setEvaluateSourceJurisdiction}
          targetJurisdiction={evaluateTargetJurisdiction}
          setTargetJurisdiction={setEvaluateTargetJurisdiction}
          jurisdictions={evaluateJurisdictions}
          setJurisdictions={setEvaluateJurisdictions}
          requireAll={evaluateRequireAll}
          setRequireAll={setEvaluateRequireAll}
          onSubmit={handleEvaluate}
          loading={loading}
          result={evaluationResult}
        />
      )}

      {/* Access Rights Tab */}
      {activeTab === "access-rights" && (
        <AccessRightsTab
          agentId={accessRightsAgentId}
          setAgentId={setAccessRightsAgentId}
          resourceId={accessRightsResourceId}
          setResourceId={setAccessRightsResourceId}
          onSubmit={handleAccessRightsLookup}
          loading={loading}
          result={accessRightsResult}
        />
      )}

      {/* Jurisdictions Tab */}
      {activeTab === "jurisdictions" && (
        <JurisdictionsTab
          jurisdictions={jurisdictionsList}
          institutions={institutionsList}
          expandedJurisdiction={expandedJurisdiction}
          setExpandedJurisdiction={setExpandedJurisdiction}
        />
      )}

      {/* Graph Explorer Tab */}
      {activeTab === "graph" && (
        <GraphExplorerTab jurisdictionCount={jurisdictionsList.length} institutionCount={institutionsList.length} />
      )}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Evaluate Tab
// ─────────────────────────────────────────────────────────────────────────────

function EvaluateTab({
  sourceId,
  setSourceId,
  targetId,
  setTargetId,
  scope,
  setScope,
  sourceJurisdiction,
  setSourceJurisdiction,
  targetJurisdiction,
  setTargetJurisdiction,
  jurisdictions,
  setJurisdictions,
  requireAll,
  setRequireAll,
  onSubmit,
  loading,
  result,
}: {
  sourceId: string;
  setSourceId: (v: string) => void;
  targetId: string;
  setTargetId: (v: string) => void;
  scope: string;
  setScope: (v: string) => void;
  sourceJurisdiction: string;
  setSourceJurisdiction: (v: string) => void;
  targetJurisdiction: string;
  setTargetJurisdiction: (v: string) => void;
  jurisdictions: string;
  setJurisdictions: (v: string) => void;
  requireAll: boolean;
  setRequireAll: (v: boolean) => void;
  onSubmit: () => void;
  loading: boolean;
  result: ConsentEvaluationResponse | null;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Form */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 3 }}>
          <Typography sx={{ mb: 2, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Query parameters
          </Typography>

          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr", lg: "1fr 1fr 1fr" } }}>
            <TextField
              label="Source ID"
              size="small"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              placeholder="Agent or subject ID"
            />
            <TextField
              label="Target ID"
              size="small"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="Resource ID"
            />
            <TextField
              label="Scope"
              size="small"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="read, write, delete"
            />
            <TextField
              label="Source Jurisdiction"
              size="small"
              value={sourceJurisdiction}
              onChange={(e) => setSourceJurisdiction(e.target.value)}
              placeholder="e.g., US"
            />
            <TextField
              label="Target Jurisdiction"
              size="small"
              value={targetJurisdiction}
              onChange={(e) => setTargetJurisdiction(e.target.value)}
              placeholder="e.g., EU"
            />
            <TextField
              label="Jurisdictions (CSV)"
              size="small"
              value={jurisdictions}
              onChange={(e) => setJurisdictions(e.target.value)}
              placeholder="US, EU, CA"
            />
          </Box>

          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={<Checkbox checked={requireAll} onChange={(e) => setRequireAll(e.target.checked)} />}
              label={<Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>Require all jurisdictions</Typography>}
            />
          </Box>

          <Button
            onClick={onSubmit}
            disabled={loading}
            variant="contained"
            sx={{ mt: 3, borderRadius: 999, bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" } }}
          >
            {loading ? "Evaluating..." : "Evaluate Consent"}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {result && <EvaluationResultDisplay result={result} />}
    </Box>
  );
}

function EvaluationResultDisplay({ result }: { result: ConsentEvaluationResponse }) {
  const jurisdictionResults = result.jurisdiction_results ?? {};
  const peerDecisions = result.peer_decisions ?? {};

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Decision Badge */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 3 }}>
          <Typography sx={{ mb: 2, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Decision
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
            <StatusBadge status={result.granted ? "granted" : "denied"} />
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              {result.reason}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Local Decision */}
      <KeyValuePanel
        title="Local Decision"
        entries={[
          { label: "Granted", value: result.local_decision?.granted ? "Yes" : "No" },
          { label: "Reason", value: result.local_decision?.reason || "—" },
        ]}
      />

      {/* Access Rights */}
      {result.access_rights && <AccessRightsDisplay rights={result.access_rights} />}

      {/* Jurisdiction Results */}
      {Object.keys(jurisdictionResults).length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 2, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Jurisdiction Results
            </Typography>
            <Box sx={{ display: "grid", gap: 1.5 }}>
            {Object.entries(jurisdictionResults).map(([code, jr]) => (
              <Card
                key={code}
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  borderColor: "var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  boxShadow: "none",
                }}
              >
                <CardContent sx={{ p: 2 }}>
                  <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                      {code}
                    </Typography>
                    <StatusBadge status={jr.satisfied ? "satisfied" : "unsatisfied"} />
                  </Box>

                  <Box component="dl" sx={{ mt: 1.5, display: "grid", gap: 0.75 }}>
                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                      <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Required Scopes
                      </Typography>
                      <Typography component="dd" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {jr.required_scopes?.join(", ") || "—"}
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                      <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Satisfied Scopes
                      </Typography>
                      <Typography component="dd" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {jr.satisfied_scopes?.join(", ") || "—"}
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                      <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Missing Scopes
                      </Typography>
                      <Typography component="dd" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {jr.missing_scopes?.join(", ") || "—"}
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                      <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Regulations
                      </Typography>
                      <Typography component="dd" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {jr.applicable_regulations?.join(", ") || "—"}
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                      <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Reason
                      </Typography>
                      <Typography component="dd" sx={{ fontSize: 12, color: "var(--app-muted)", textAlign: "right" }}>
                        {jr.reason}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Peer Decisions */}
      {Object.keys(peerDecisions).length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 2, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Peer Decisions
            </Typography>
            <Box sx={{ display: "grid", gap: 1 }}>
            {Object.entries(peerDecisions).map(([peer, decision]) => (
              <Card
                key={peer}
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  borderColor: "var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  boxShadow: "none",
                }}
              >
                <CardContent sx={{ p: 1.75, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                    {peer}
                  </Typography>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <StatusBadge status={decision.granted ? "granted" : "denied"} />
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      {decision.reason}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Evaluated At */}
      <KeyValuePanel
        entries={[
          {
            label: "Evaluated At",
            value: result.evaluated_at ? new Date(result.evaluated_at).toLocaleString() : "—",
          },
        ]}
      />
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Access Rights Tab
// ─────────────────────────────────────────────────────────────────────────────

function AccessRightsTab({
  agentId,
  setAgentId,
  resourceId,
  setResourceId,
  onSubmit,
  loading,
  result,
}: {
  agentId: string;
  setAgentId: (v: string) => void;
  resourceId: string;
  setResourceId: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
  result: ConsentAccessRights | null;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 3 }}>
          <Typography sx={{ mb: 2, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Lookup
          </Typography>

          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <TextField
              label="Agent ID"
              size="small"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="e.g., agent-123"
            />
            <TextField
              label="Resource ID"
              size="small"
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              placeholder="e.g., resource-456"
            />
          </Box>

          <Button
            onClick={onSubmit}
            disabled={loading}
            variant="contained"
            sx={{ mt: 3, borderRadius: 999, bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)", "&:hover": { bgcolor: "var(--app-accent)" } }}
          >
            {loading ? "Loading..." : "Lookup Access Rights"}
          </Button>
        </CardContent>
      </Card>

      {result && <AccessRightsDisplay rights={result} />}
    </Box>
  );
}

function AccessRightsDisplay({ rights }: { rights: ConsentAccessRights }) {
  const jurisdictionConstraints = rights.jurisdiction_constraints ?? {};

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <KeyValuePanel
        title="Resource Access"
        entries={[
          { label: "Agent ID", value: rights.agent_id },
          { label: "Resource ID", value: rights.resource_id },
          {
            label: "Expires At",
            value: rights.expires_at ? new Date(rights.expires_at).toLocaleString() : "Never",
          },
        ]}
      />

      {/* Allowed Scopes */}
      {rights.allowed_scopes && rights.allowed_scopes.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Allowed Scopes
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {rights.allowed_scopes.map((scope) => (
              <StatusBadge key={scope} status={scope} />
            ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Jurisdiction Constraints */}
      {Object.keys(jurisdictionConstraints).length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Jurisdiction Constraints
            </Typography>
            <Box sx={{ display: "grid", gap: 1 }}>
            {Object.entries(jurisdictionConstraints).map(([jurisdiction, constraints]) => (
              <Card
                key={jurisdiction}
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  borderColor: "var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  boxShadow: "none",
                }}
              >
                <CardContent sx={{ py: 1.25, px: 1.5 }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 700, color: "var(--app-fg)" }}>
                    {jurisdiction}
                  </Typography>
                  <Typography sx={{ mt: 0.25, fontSize: 12, color: "var(--app-muted)" }}>
                    {constraints.join(", ")}
                  </Typography>
                </CardContent>
              </Card>
            ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Conditions */}
      {rights.conditions && rights.conditions.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Conditions
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2, display: "grid", gap: 0.5 }}>
            {rights.conditions.map((condition, i) => (
              <Typography key={i} component="li" sx={{ fontSize: 13, color: "var(--app-muted)" }}>
                {condition}
              </Typography>
            ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Grant Sources */}
      {rights.grant_sources && rights.grant_sources.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Grant Sources
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {rights.grant_sources.map((source) => (
              <StatusBadge key={source} status={source} />
            ))}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Jurisdictions Tab
// ─────────────────────────────────────────────────────────────────────────────

function JurisdictionsTab({
  jurisdictions,
  institutions,
  expandedJurisdiction,
  setExpandedJurisdiction,
}: {
  jurisdictions: (JurisdictionPolicy & { id: string })[];
  institutions: { id: string; jurisdiction_code: string }[];
  expandedJurisdiction: string | null;
  setExpandedJurisdiction: (id: string | null) => void;
}) {
  const jurisdictionColumns: Column<JurisdictionPolicy & { id: string }>[] = [
    {
      key: "jurisdiction_code",
      header: "Code",
      render: (row) => (
        <Typography component="span" sx={{ fontWeight: 800 }}>
          {row.jurisdiction_code}
        </Typography>
      ),
    },
    {
      key: "applicable_regulations",
      header: "Regulations",
      render: (row) => row.applicable_regulations?.join(", ") || "—",
    },
    {
      key: "required_consent_scopes",
      header: "Consent Scopes",
      render: (row) => row.required_consent_scopes?.join(", ") || "—",
    },
    {
      key: "requires_explicit_consent",
      header: "Explicit Consent",
      render: (row) => (row.requires_explicit_consent ? "Yes" : "No"),
    },
    {
      key: "data_residency_required",
      header: "Data Residency",
      render: (row) => (row.data_residency_required ? "Yes" : "No"),
    },
  ];

  const institutionColumns: Column<{ id: string; jurisdiction_code: string }>[] = [
    {
      key: "id",
      header: "Institution ID",
      render: (row) => (
        <Typography component="span" sx={{ fontWeight: 800 }}>
          {row.id}
        </Typography>
      ),
    },
    {
      key: "jurisdiction_code",
      header: "Jurisdiction",
      render: (row) => row.jurisdiction_code,
    },
  ];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Jurisdictions Table */}
      <Box>
        <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Jurisdictions
        </Typography>
        <DataTable
          data={jurisdictions}
          columns={jurisdictionColumns}
          onRowClick={(row) => setExpandedJurisdiction(expandedJurisdiction === row.id ? null : row.id)}
          emptyMessage="No jurisdictions found"
        />
      </Box>

      {/* Expanded Jurisdiction Details */}
      {expandedJurisdiction && (
        (() => {
          const jurisdiction = jurisdictions.find((j) => j.id === expandedJurisdiction);
          if (!jurisdiction) return null;
          return (
            <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
              <CardContent sx={{ p: 2.5 }}>
                <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                  {jurisdiction.jurisdiction_code} Details
                </Typography>
                <Box component="dl" sx={{ display: "grid", gap: 1 }}>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>ID</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)" }}>{jurisdiction.id}</Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>Code</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)" }}>{jurisdiction.jurisdiction_code}</Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>Regulations</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)", textAlign: "right" }}>
                      {jurisdiction.applicable_regulations?.join(", ") || "—"}
                    </Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>Consent Scopes</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)", textAlign: "right" }}>
                      {jurisdiction.required_consent_scopes?.join(", ") || "—"}
                    </Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>Explicit Consent Required</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)" }}>{jurisdiction.requires_explicit_consent ? "Yes" : "No"}</Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                    <Typography component="dt" sx={{ fontSize: 13, color: "var(--app-muted)" }}>Data Residency Required</Typography>
                    <Typography component="dd" sx={{ fontSize: 13, color: "var(--app-fg)" }}>{jurisdiction.data_residency_required ? "Yes" : "No"}</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          );
        })()
      )}

      {/* Institutions Table */}
      <Box>
        <Typography sx={{ mb: 1.5, fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Institutions
        </Typography>
        <DataTable
          data={institutions}
          columns={institutionColumns}
          emptyMessage="No institutions found"
        />
      </Box>
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph Explorer Tab
// ─────────────────────────────────────────────────────────────────────────────

function GraphExplorerTab({
  jurisdictionCount,
  institutionCount,
}: {
  jurisdictionCount: number;
  institutionCount: number;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Stats */}
      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
        <MetricCard label="Jurisdictions" value={jurisdictionCount} accent />
        <MetricCard label="Institutions" value={institutionCount} accent />
      </Box>

      {/* Placeholder */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 4 }}>
          <Typography sx={{ textAlign: "center", fontSize: 14, fontWeight: 700, color: "var(--app-muted)" }}>
            Consent graph visualization
          </Typography>
          <Typography sx={{ mt: 1, textAlign: "center", fontSize: 13, color: "var(--app-muted)" }}>
            Connect subjects, resources, and institutions to visualize consent relationships
          </Typography>

          <Box sx={{ mt: 3, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Box
              key={i}
              sx={{
                height: 80,
                borderRadius: 2,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
              }}
            />
          ))}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

"use client";

import { useState } from "react";
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
    <div className="flex flex-col gap-6">
      <TabBar tabs={tabs} activeTab={activeTab} onTabChange={(key) => setActiveTab(key as TabKey)} />

      {error && (
        <div className="rounded-3xl bg-red-500/10 p-4 ring-1 ring-red-700/60">
          <p className="text-[12px] text-red-200">{error}</p>
        </div>
      )}

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
    </div>
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
    <div className="flex flex-col gap-6">
      {/* Form */}
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Query parameters
        </p>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Source ID</label>
            <input
              type="text"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              placeholder="Agent or subject ID"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Target ID</label>
            <input
              type="text"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="Resource ID"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Scope</label>
            <input
              type="text"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="read, write, delete"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Source Jurisdiction</label>
            <input
              type="text"
              value={sourceJurisdiction}
              onChange={(e) => setSourceJurisdiction(e.target.value)}
              placeholder="e.g., US"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Target Jurisdiction</label>
            <input
              type="text"
              value={targetJurisdiction}
              onChange={(e) => setTargetJurisdiction(e.target.value)}
              placeholder="e.g., EU"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Jurisdictions (CSV)</label>
            <input
              type="text"
              value={jurisdictions}
              onChange={(e) => setJurisdictions(e.target.value)}
              placeholder="US, EU, CA"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <input
            type="checkbox"
            id="require-all"
            checked={requireAll}
            onChange={(e) => setRequireAll(e.target.checked)}
            className="h-4 w-4 rounded"
          />
          <label htmlFor="require-all" className="text-[11px] text-[--app-muted]">
            Require all jurisdictions
          </label>
        </div>

        <button
          onClick={onSubmit}
          disabled={loading}
          className="mt-6 rounded-full bg-[--app-accent] px-6 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Evaluating..." : "Evaluate Consent"}
        </button>
      </div>

      {/* Results */}
      {result && <EvaluationResultDisplay result={result} />}
    </div>
  );
}

function EvaluationResultDisplay({ result }: { result: ConsentEvaluationResponse }) {
  const jurisdictionResults = result.jurisdiction_results ?? {};
  const peerDecisions = result.peer_decisions ?? {};

  return (
    <div className="flex flex-col gap-4">
      {/* Decision Badge */}
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Decision
        </p>
        <div className="flex items-center gap-3">
          <StatusBadge status={result.granted ? "granted" : "denied"} className="text-base" />
          <p className="text-[12px] text-[--app-muted]">{result.reason}</p>
        </div>
      </div>

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
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Jurisdiction Results
          </p>
          <div className="space-y-3">
            {Object.entries(jurisdictionResults).map(([code, jr]) => (
              <div key={code} className="rounded-lg border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[11px] font-medium text-[--app-fg]">{code}</p>
                  <StatusBadge status={jr.satisfied ? "satisfied" : "unsatisfied"} />
                </div>
                <dl className="space-y-1 text-[10px] text-[--app-muted]">
                  <div className="flex justify-between">
                    <dt>Required Scopes:</dt>
                    <dd>{jr.required_scopes?.join(", ") || "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Satisfied Scopes:</dt>
                    <dd>{jr.satisfied_scopes?.join(", ") || "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Missing Scopes:</dt>
                    <dd>{jr.missing_scopes?.join(", ") || "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Regulations:</dt>
                    <dd>{jr.applicable_regulations?.join(", ") || "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Reason:</dt>
                    <dd>{jr.reason}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Peer Decisions */}
      {Object.keys(peerDecisions).length > 0 && (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Peer Decisions
          </p>
          <div className="space-y-2">
            {Object.entries(peerDecisions).map(([peer, decision]) => (
              <div key={peer} className="flex items-center justify-between rounded-lg border border-[--app-border] bg-[--app-control-bg] p-2 ring-1 ring-[--app-surface-ring]">
                <p className="text-[11px] font-medium text-[--app-fg]">{peer}</p>
                <div className="flex items-center gap-2">
                  <StatusBadge status={decision.granted ? "granted" : "denied"} />
                  <p className="text-[10px] text-[--app-muted]">{decision.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
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
    </div>
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
    <div className="flex flex-col gap-6">
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Lookup
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Agent ID</label>
            <input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="e.g., agent-123"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>

          <div>
            <label className="text-[10px] font-medium text-[--app-muted]">Resource ID</label>
            <input
              type="text"
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              placeholder="e.g., resource-456"
              className="mt-1 w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:outline-none focus:ring-2 focus:ring-[--app-accent]"
            />
          </div>
        </div>

        <button
          onClick={onSubmit}
          disabled={loading}
          className="mt-6 rounded-full bg-[--app-accent] px-6 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Lookup Access Rights"}
        </button>
      </div>

      {result && <AccessRightsDisplay rights={result} />}
    </div>
  );
}

function AccessRightsDisplay({ rights }: { rights: ConsentAccessRights }) {
  const jurisdictionConstraints = rights.jurisdiction_constraints ?? {};

  return (
    <div className="flex flex-col gap-4">
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
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Allowed Scopes
          </p>
          <div className="flex flex-wrap gap-2">
            {rights.allowed_scopes.map((scope) => (
              <StatusBadge key={scope} status={scope} />
            ))}
          </div>
        </div>
      )}

      {/* Jurisdiction Constraints */}
      {Object.keys(jurisdictionConstraints).length > 0 && (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Jurisdiction Constraints
          </p>
          <div className="space-y-2">
            {Object.entries(jurisdictionConstraints).map(([jurisdiction, constraints]) => (
              <div key={jurisdiction} className="rounded-lg border border-[--app-border] bg-[--app-control-bg] p-2 ring-1 ring-[--app-surface-ring]">
                <p className="text-[10px] font-medium text-[--app-fg]">{jurisdiction}</p>
                <p className="text-[10px] text-[--app-muted]">{constraints.join(", ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conditions */}
      {rights.conditions && rights.conditions.length > 0 && (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Conditions
          </p>
          <ul className="space-y-1">
            {rights.conditions.map((condition, i) => (
              <li key={i} className="text-[11px] text-[--app-muted]">
                • {condition}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Grant Sources */}
      {rights.grant_sources && rights.grant_sources.length > 0 && (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Grant Sources
          </p>
          <div className="flex flex-wrap gap-2">
            {rights.grant_sources.map((source) => (
              <StatusBadge key={source} status={source} />
            ))}
          </div>
        </div>
      )}
    </div>
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
      render: (row) => <span className="font-medium">{row.jurisdiction_code}</span>,
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
      render: (row) => <span className="font-medium">{row.id}</span>,
    },
    {
      key: "jurisdiction_code",
      header: "Jurisdiction",
      render: (row) => row.jurisdiction_code,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Jurisdictions Table */}
      <div>
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Jurisdictions
        </p>
        <DataTable
          data={jurisdictions}
          columns={jurisdictionColumns}
          onRowClick={(row) => setExpandedJurisdiction(expandedJurisdiction === row.id ? null : row.id)}
          emptyMessage="No jurisdictions found"
        />
      </div>

      {/* Expanded Jurisdiction Details */}
      {expandedJurisdiction && (
        (() => {
          const jurisdiction = jurisdictions.find((j) => j.id === expandedJurisdiction);
          if (!jurisdiction) return null;
          return (
            <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                {jurisdiction.jurisdiction_code} Details
              </p>
              <dl className="space-y-2">
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">ID</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">Code</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.jurisdiction_code}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">Regulations</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.applicable_regulations?.join(", ") || "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">Consent Scopes</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.required_consent_scopes?.join(", ") || "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">Explicit Consent Required</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.requires_explicit_consent ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[11px] text-[--app-muted]">Data Residency Required</dt>
                  <dd className="text-[11px] text-[--app-fg]">{jurisdiction.data_residency_required ? "Yes" : "No"}</dd>
                </div>
              </dl>
            </div>
          );
        })()
      )}

      {/* Institutions Table */}
      <div>
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Institutions
        </p>
        <DataTable
          data={institutions}
          columns={institutionColumns}
          emptyMessage="No institutions found"
        />
      </div>
    </div>
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
    <div className="flex flex-col gap-4">
      {/* Stats */}
      <div className="grid gap-3 md:grid-cols-2">
        <MetricCard label="Jurisdictions" value={jurisdictionCount} accent />
        <MetricCard label="Institutions" value={institutionCount} accent />
      </div>

      {/* Placeholder */}
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-8 ring-1 ring-[--app-surface-ring]">
        <p className="text-center text-[12px] font-medium text-[--app-muted]">
          Consent graph visualization
        </p>
        <p className="mt-2 text-center text-[11px] text-[--app-muted]">
          Connect subjects, resources, and institutions to visualize consent relationships
        </p>

        {/* Grid placeholder */}
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-lg border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring]" />
          ))}
        </div>
      </div>
    </div>
  );
}

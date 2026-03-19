"use client";

import { useState } from "react";
import {
  StatusBadge,
  MetricCard,
  KeyValuePanel,
  JsonViewer,
  TabBar,
  LoadingState,
  EmptyState,
  DataTable,
  ThreatGauge,
} from "@/components/security";
import type { Column } from "@/components/security";

const BACKEND = "";

interface IntrospectionResult {
  actor_id: string;
  threat_score: number;
  threat_level: "info" | "low" | "medium" | "high" | "critical";
  compliance_status: "compliant" | "warning" | "violation";
  verdict: "PROCEED" | "THROTTLE" | "REQUIRE_CONFIRMATION" | "HALT";
  assessed_at: string;
  drift_summary?: {
    info?: number;
    low?: number;
    medium?: number;
    high?: number;
    critical?: number;
  };
  active_escalations?: string[];
  active_constraints?: string[];
}

interface VerdictResult {
  verdict: "PROCEED" | "THROTTLE" | "REQUIRE_CONFIRMATION" | "HALT";
  explanation: string;
  actor_id: string;
  operation: string;
  confidence: number;
}

interface AccountabilityEntry {
  type: string;
  actor_id: string;
  threat_level: string;
  compliance_status: string;
  verdict: string;
  timestamp: string;
  [key: string]: unknown;
}

interface HealthComponent {
  name: string;
  status: "ok" | "not_configured";
  [key: string]: unknown;
}

interface HealthResult {
  overall_status: "ok" | "not_configured" | "degraded";
  component_count: number;
  components?: HealthComponent[];
  timestamp?: string;
}

interface ReflexiveManagerProps {
  initialAccountability?: AccountabilityEntry[];
  initialHealth?: HealthResult;
}

const SEVERITY_COLORS = {
  info: "bg-[--app-accent] text-[--app-accent-contrast]",
  low: "bg-sky-600/60 text-sky-50",
  medium: "bg-amber-600/60 text-amber-50",
  high: "bg-orange-600/60 text-orange-50",
  critical: "bg-red-600/60 text-red-50",
};

const SEVERITY_BAR_COLORS = {
  info: "bg-[--app-accent]",
  low: "bg-sky-500",
  medium: "bg-amber-500",
  high: "bg-orange-500",
  critical: "bg-red-500",
};

export function ReflexiveManager({
  initialAccountability = [],
  initialHealth,
}: ReflexiveManagerProps) {
  const [activeTab, setActiveTab] = useState("introspection");

  // Introspection tab state
  const [introspectActorId, setIntrospectActorId] = useState("");
  const [introspectionLoading, setIntrospectionLoading] = useState(false);
  const [introspectionResult, setIntrospectionResult] =
    useState<IntrospectionResult | null>(null);
  const [introspectionError, setIntrospectionError] = useState<string | null>(
      null
    );

  // Verdicts tab state
  const [verdictActorId, setVerdictActorId] = useState("");
  const [verdictOperation, setVerdictOperation] = useState("call_tool");
  const [verdictResourceId, setVerdictResourceId] = useState("");
  const [verdictLoading, setVerdictLoading] = useState(false);
  const [verdictResult, setVerdictResult] = useState<VerdictResult | null>(
      null
    );
  const [verdictError, setVerdictError] = useState<string | null>(null);

  // Accountability tab state
  const [accountabilityFilter, setAccountabilityFilter] = useState("");
  const [expandedAccountabilityRow, setExpandedAccountabilityRow] = useState<
    number | null
  >(null);

  // Handle introspection request
  const handleIntrospect = async () => {
    if (!introspectActorId.trim()) {
      setIntrospectionError("Please enter an actor ID");
      return;
    }

    setIntrospectionLoading(true);
    setIntrospectionError(null);
    setIntrospectionResult(null);

    try {
      const response = await fetch(
        `${BACKEND}/security/reflexive/introspect/${encodeURIComponent(introspectActorId)}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = (await response.json()) as IntrospectionResult;
      setIntrospectionResult(data);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      if (errorMessage.includes("fetch") || errorMessage.includes("Failed")) {
        setIntrospectionError(
          "Could not reach the security API. Make sure the backend is running."
        );
      } else {
        setIntrospectionError(`Failed to introspect: ${errorMessage}`);
      }
    } finally {
      setIntrospectionLoading(false);
    }
  };

  // Handle verdict check
  const handleCheckVerdict = async () => {
    if (!verdictActorId.trim()) {
      setVerdictError("Please enter an actor ID");
      return;
    }

    setVerdictLoading(true);
    setVerdictError(null);
    setVerdictResult(null);

    try {
      const params = new URLSearchParams({
        actor_id: verdictActorId,
        operation: verdictOperation,
      });

      if (verdictResourceId.trim()) {
        params.append("resource_id", verdictResourceId);
      }

      const response = await fetch(
        `${BACKEND}/security/reflexive/verdict?${params.toString()}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = (await response.json()) as VerdictResult;
      setVerdictResult(data);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      if (errorMessage.includes("fetch") || errorMessage.includes("Failed")) {
        setVerdictError(
          "Could not reach the security API. Make sure the backend is running."
        );
      } else {
        setVerdictError(`Failed to check verdict: ${errorMessage}`);
      }
    } finally {
      setVerdictLoading(false);
    }
  };

  // Render drift summary chart
  const renderDriftSummary = (
    driftData?: IntrospectionResult["drift_summary"]
  ) => {
    if (!driftData || Object.keys(driftData).length === 0) {
      return <p className="text-[12px] text-[--app-muted]">No drift detected</p>;
    }

    const total = Object.values(driftData).reduce((a, b) => a + (b || 0), 0);

    if (total === 0) {
      return <p className="text-[12px] text-[--app-muted]">No drift detected</p>;
    }

    const severities = ["critical", "high", "medium", "low", "info"] as const;
    const maxCount = Math.max(...Object.values(driftData));

    return (
      <div className="space-y-2">
        {severities.map((severity) => {
          const count = driftData[severity] || 0;
          const percentage = (count / maxCount) * 100;

          return (
            <div key={severity} className="flex items-center gap-3">
              <span className="w-16 text-[11px] font-medium capitalize text-[--app-muted]">
                {severity}
              </span>
              <div className="flex-1 rounded-full bg-[--app-control-bg] h-6 overflow-hidden ring-1 ring-[--app-surface-ring]">
                {percentage > 0 && (
                  <div
                    className={`h-full transition-all ${SEVERITY_BAR_COLORS[severity]}`}
                    style={{ width: `${percentage}%` }}
                  />
                )}
              </div>
              <span className="w-8 text-right text-[11px] text-[--app-muted]">
                {count}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  // Constraint badge renderer
  const renderConstraintBadge = (constraint: string) => {
    const labels: Record<string, string> = {
      sandbox_required: "🔒 Sandbox",
      audit_all_outputs: "📝 Audit",
      human_confirmation_required: "👤 Confirm",
      rate_limited: "⏱️ Rate Limited",
      enhanced_logging: "📊 Enhanced Log",
    };

    return (
      <span
        key={constraint}
        className="inline-flex items-center gap-1.5 rounded-full bg-[--app-control-bg] px-2.5 py-1 text-[11px] font-medium text-[--app-muted] ring-1 ring-[--app-surface-ring]"
      >
        {labels[constraint] || constraint}
      </span>
    );
  };

  // Introspection tab content
  const renderIntrospectionTab = () => (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="actor_id (e.g., agent-123, user-456)"
          value={introspectActorId}
          onChange={(e) => setIntrospectActorId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleIntrospect()}
          className="flex-1 rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none"
        />
        <button
          onClick={handleIntrospect}
          disabled={introspectionLoading}
          className="rounded-full bg-[--app-accent] px-4 py-1.5 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
        >
          {introspectionLoading ? "Loading..." : "Inspect"}
        </button>
      </div>

      {introspectionError && (
        <div className="rounded-3xl bg-red-950/40 p-4 ring-1 ring-red-700/60">
          <p className="text-[12px] text-red-100">{introspectionError}</p>
        </div>
      )}

      {introspectionLoading && <LoadingState message="Introspecting actor..." />}

      {introspectionResult && (
        <div className="space-y-4">
          <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
            <div className="flex items-center gap-4">
              <ThreatGauge
                level={introspectionResult.threat_level}
                score={introspectionResult.threat_score}
              />
              <div className="space-y-2">
                <StatusBadge
                  status={introspectionResult.compliance_status}
                />
                <StatusBadge status={introspectionResult.verdict} />
              </div>
            </div>
          </div>

          <KeyValuePanel
            title="Introspection Details"
            entries={[
              { label: "Actor ID", value: introspectionResult.actor_id },
              { label: "Threat Score", value: introspectionResult.threat_score.toFixed(2) },
              { label: "Threat Level", value: introspectionResult.threat_level },
              { label: "Compliance Status", value: introspectionResult.compliance_status },
              { label: "Verdict", value: introspectionResult.verdict },
              { label: "Assessed At", value: introspectionResult.assessed_at },
            ]}
          />

          {introspectionResult.drift_summary && (
            <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted] mb-3">
                Drift Summary
              </h3>
              {renderDriftSummary(introspectionResult.drift_summary)}
            </div>
          )}

          {introspectionResult.active_escalations &&
            introspectionResult.active_escalations.length > 0 && (
              <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted] mb-3">
                  Active Escalations
                </h3>
                <div className="space-y-2">
                  {introspectionResult.active_escalations.map((esc, i) => (
                    <StatusBadge key={i} status={esc} />
                  ))}
                </div>
              </div>
            )}

          {introspectionResult.active_constraints &&
            introspectionResult.active_constraints.length > 0 && (
              <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted] mb-3">
                  Active Constraints
                </h3>
                <div className="flex flex-wrap gap-2">
                  {introspectionResult.active_constraints.map((constraint) =>
                    renderConstraintBadge(constraint)
                  )}
                </div>
              </div>
            )}

          <JsonViewer
            title="Raw Introspection Data"
            data={introspectionResult}
          />
        </div>
      )}

      {!introspectionLoading && !introspectionResult && !introspectionError && (
        <EmptyState title="No Actor Introspected" message="Enter an actor ID and click Inspect to view detailed behavior analysis." />
      )}
    </div>
  );

  // Verdicts tab content
  const renderVerdictsTab = () => (
    <div className="space-y-4">
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted] mb-3">
          Check Execution Verdict
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-[--app-muted] mb-1">
              Actor ID
            </label>
            <input
              type="text"
              placeholder="e.g., agent-123"
              value={verdictActorId}
              onChange={(e) => setVerdictActorId(e.target.value)}
              className="w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[--app-muted] mb-1">
              Operation
            </label>
            <select
              value={verdictOperation}
              onChange={(e) => setVerdictOperation(e.target.value)}
              className="w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none"
            >
              <option value="call_tool">Call Tool</option>
              <option value="read_resource">Read Resource</option>
              <option value="get_prompt">Get Prompt</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[--app-muted] mb-1">
              Resource ID (optional)
            </label>
            <input
              type="text"
              placeholder="e.g., resource-456"
              value={verdictResourceId}
              onChange={(e) => setVerdictResourceId(e.target.value)}
              className="w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none"
            />
          </div>

          <button
            onClick={handleCheckVerdict}
            disabled={verdictLoading}
            className="w-full rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-50"
          >
            {verdictLoading ? "Checking..." : "Check Verdict"}
          </button>
        </div>
      </div>

      {verdictError && (
        <div className="rounded-3xl bg-red-950/40 p-4 ring-1 ring-red-700/60">
          <p className="text-[12px] text-red-100">{verdictError}</p>
        </div>
      )}

      {verdictLoading && <LoadingState message="Checking verdict..." />}

      {verdictResult && (
        <div className="space-y-4">
          <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring] text-center">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted] mb-3">
              Verdict
            </p>
            <div
              className={`inline-block rounded-full px-6 py-3 text-sm font-bold ${
                verdictResult.verdict === "PROCEED"
                  ? "bg-[--app-accent] text-[--app-accent-contrast]"
                  : verdictResult.verdict === "THROTTLE"
                    ? "bg-amber-600/80 text-amber-50"
                    : verdictResult.verdict === "REQUIRE_CONFIRMATION"
                      ? "bg-orange-600/80 text-orange-50"
                      : "bg-red-600/80 text-red-50"
              }`}
            >
              {verdictResult.verdict}
            </div>
            <p className="mt-4 text-[12px] text-[--app-muted]">
              {verdictResult.explanation}
            </p>
            <p className="mt-2 text-[11px] text-[--app-muted]">
              Confidence: {(verdictResult.confidence * 100).toFixed(1)}%
            </p>
          </div>

          <KeyValuePanel
            title="Verdict Details"
            entries={[
              { label: "Actor ID", value: verdictResult.actor_id },
              { label: "Operation", value: verdictResult.operation },
              { label: "Verdict", value: verdictResult.verdict },
              { label: "Confidence", value: (verdictResult.confidence * 100).toFixed(1) + "%" },
            ]}
          />

          <JsonViewer title="Raw Verdict Data" data={verdictResult} />
        </div>
      )}

      {!verdictLoading && !verdictResult && !verdictError && (
        <EmptyState title="No Verdict Checked" message="Fill in the form and click Check Verdict to evaluate execution permissions." />
      )}
    </div>
  );

  // Accountability tab content
  const filteredAccountability = accountabilityFilter
    ? initialAccountability.filter((entry) =>
        entry.actor_id
          .toLowerCase()
          .includes(accountabilityFilter.toLowerCase())
      )
    : initialAccountability;

  const accountabilityColumns: Column<AccountabilityEntry>[] = [
    { key: "type", header: "Type" },
    { key: "actor_id", header: "Actor ID" },
    { key: "threat_level", header: "Threat Level" },
    { key: "compliance_status", header: "Compliance" },
    { key: "verdict", header: "Verdict" },
    { key: "timestamp", header: "Timestamp" },
  ];

  const renderAccountabilityTab = () => (
    <div className="space-y-4">
      <input
        type="text"
        placeholder="Filter by actor ID..."
        value={accountabilityFilter}
        onChange={(e) => setAccountabilityFilter(e.target.value)}
        className="w-full rounded-xl bg-[--app-chrome-bg] px-3 py-2 text-[12px] text-[--app-fg] ring-1 ring-[--app-border] focus:ring-2 focus:ring-[--app-accent] focus:outline-none"
      />

      {filteredAccountability.length === 0 ? (
        <EmptyState title="No Log Entries" message="No accountability log entries to display." />
      ) : (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] ring-1 ring-[--app-surface-ring] overflow-hidden">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-[--app-border] bg-[--app-hover-bg]">
                {accountabilityColumns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-2 text-left font-semibold text-[--app-muted]"
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredAccountability.map((entry, idx) => (
                <tr key={idx}>
                  <td
                    colSpan={accountabilityColumns.length}
                    className="border-b border-[--app-border]"
                  >
                    <button
                      onClick={() =>
                        setExpandedAccountabilityRow(
                          expandedAccountabilityRow === idx ? null : idx
                        )
                      }
                      className="w-full text-left px-4 py-2 hover:bg-[--app-hover-bg] transition"
                    >
                      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
                        {accountabilityColumns.map((col) => {
                          let cellContent: React.ReactNode = String(entry[col.key]);

                          if (
                            col.key === "threat_level" ||
                            col.key === "compliance_status" ||
                            col.key === "verdict"
                          ) {
                            cellContent = (
                              <StatusBadge
                                status={String(entry[col.key])}
                              />
                            );
                          }

                          return (
                            <span
                              key={col.key}
                              className="text-[--app-muted] truncate"
                            >
                              {cellContent}
                            </span>
                          );
                        })}
                      </div>
                    </button>

                    {expandedAccountabilityRow === idx && (
                      <div className="border-t border-[--app-border] bg-[--app-control-bg] px-4 py-3">
                        <JsonViewer title="Full Entry" data={entry} />
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  // Health tab content
  const renderHealthTab = () => {
    if (!initialHealth) {
      return <EmptyState title="No Health Data" message="No health data available." />;
    }

    const components = initialHealth.components || [];
    const overallStatus = initialHealth.overall_status;

    return (
      <div className="space-y-4">
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
          <div className="space-y-3">
            <div>
              <p className="text-[11px] font-medium text-[--app-muted] mb-1">
                Overall Status
              </p>
              <StatusBadge status={overallStatus} />
            </div>
            <div>
              <p className="text-[11px] font-medium text-[--app-muted] mb-1">
                Components Configured
              </p>
              <p className="text-[12px] text-[--app-muted]">
                {initialHealth.component_count}
              </p>
            </div>
            {initialHealth.timestamp && (
              <div>
                <p className="text-[11px] font-medium text-[--app-muted] mb-1">
                  Last Updated
                </p>
                <p className="text-[12px] text-[--app-muted]">
                  {new Date(initialHealth.timestamp).toLocaleString()}
                </p>
              </div>
            )}
          </div>
        </div>

        {components.length === 0 ? (
          <EmptyState title="No Components" message="No health components available." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {components.map((component, idx) => (
              <MetricCard
                key={idx}
                label={component.name}
                value={
                  component.status === "ok"
                    ? "✓ Operational"
                    : "⚠ Not Configured"
                }
              />
            ))}
          </div>
        )}
      </div>
    );
  };

  const tabs = [
    { key: "introspection", label: "Introspection" },
    { key: "verdicts", label: "Verdicts" },
    { key: "accountability", label: "Accountability" },
    { key: "health", label: "Health" },
  ];

  return (
    <div className="space-y-4">
      <TabBar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        {activeTab === "introspection" && renderIntrospectionTab()}
        {activeTab === "verdicts" && renderVerdictsTab()}
        {activeTab === "accountability" && renderAccountabilityTab()}
        {activeTab === "health" && renderHealthTab()}
      </div>
    </div>
  );
}

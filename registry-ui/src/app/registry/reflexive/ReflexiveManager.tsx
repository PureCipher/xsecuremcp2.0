"use client";

import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";
import {
  StatusBadge,
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

interface ReflexiveManagerProps {
  initialAccountability?: AccountabilityEntry[];
}

const SEVERITY_COLORS = {
  info: { bgcolor: "var(--app-accent)", color: "var(--app-accent-contrast)" },
  low: { bgcolor: "rgba(14, 165, 233, 0.12)", color: "#0369a1" },
  medium: { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" },
  high: { bgcolor: "rgba(249, 115, 22, 0.12)", color: "#c2410c" },
  critical: { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" },
};

const SEVERITY_BAR_COLORS = {
  info: "var(--app-accent)",
  low: "#0284c7",
  medium: "#d97706",
  high: "#ea580c",
  critical: "#ef4444",
};

const sectionTitleSx = {
  mb: 1.5,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: "var(--app-muted)",
};

export function ReflexiveManager({
  initialAccountability = [],
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
      return (
        <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
          No drift detected
        </Typography>
      );
    }

    const total = Object.values(driftData).reduce((a, b) => a + (b || 0), 0);

    if (total === 0) {
      return (
        <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
          No drift detected
        </Typography>
      );
    }

    const severities = ["critical", "high", "medium", "low", "info"] as const;
    const maxCount = Math.max(...Object.values(driftData));

    return (
      <Box sx={{ display: "grid", gap: 1 }}>
        {severities.map((severity) => {
          const count = driftData[severity] || 0;
          const percentage = (count / maxCount) * 100;

          return (
            <Box
              key={severity}
              sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
            >
              <Typography
                sx={{
                  width: 84,
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: "capitalize",
                  color: "var(--app-muted)",
                }}
              >
                {severity}
              </Typography>

              <Box
                sx={{
                  flex: 1,
                  height: 12,
                  borderRadius: 1,
                  bgcolor: "var(--app-control-bg)",
                  border: "1px solid var(--app-border)",
                  overflow: "hidden",
                }}
              >
                {percentage > 0 ? (
                  <Box
                    sx={{
                      height: "100%",
                      width: `${percentage}%`,
                      bgcolor: SEVERITY_BAR_COLORS[severity],
                      transition: "width 160ms ease",
                    }}
                  />
                ) : null}
              </Box>

              <Typography
                sx={{
                  width: 28,
                  textAlign: "right",
                  fontSize: 12,
                  color: "var(--app-muted)",
                }}
              >
                {count}
              </Typography>
            </Box>
          );
        })}
      </Box>
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
      <Chip
        key={constraint}
        label={labels[constraint] || constraint}
        size="small"
        sx={{
          bgcolor: "var(--app-control-bg)",
          border: "1px solid var(--app-border)",
          color: "var(--app-muted)",
          fontWeight: 700,
        }}
      />
    );
  };

  // Introspection tab content
  const renderIntrospectionTab = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
        <TextField
          fullWidth
          size="small"
          label="Actor ID"
          placeholder="actor_id (e.g., agent-123, user-456)"
          value={introspectActorId}
          onChange={(e) => setIntrospectActorId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleIntrospect()}
          sx={{ flex: 1, minWidth: 260 }}
        />
        <Button
          onClick={handleIntrospect}
          disabled={introspectionLoading}
          variant="contained"
          sx={{
            bgcolor: "var(--app-accent)",
            color: "var(--app-accent-contrast)",
            px: 3,
            "&:hover": { bgcolor: "var(--app-accent)" },
          }}
        >
          {introspectionLoading ? "Loading..." : "Inspect"}
        </Button>
      </Box>

      {introspectionError ? <Alert severity="error">{introspectionError}</Alert> : null}

      {introspectionLoading && <LoadingState message="Introspecting actor..." />}

      {introspectionResult && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Card variant="outlined">
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <ThreatGauge
                level={introspectionResult.threat_level}
                score={introspectionResult.threat_score}
              />
              <Box sx={{ display: "grid", gap: 1 }}>
                <StatusBadge
                  status={introspectionResult.compliance_status}
                />
                <StatusBadge status={introspectionResult.verdict} />
              </Box>
              </Box>
            </CardContent>
          </Card>

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
            <Card variant="outlined">
              <CardContent sx={{ p: 2.5 }}>
              <Typography sx={sectionTitleSx}>
                Drift Summary
              </Typography>
              {renderDriftSummary(introspectionResult.drift_summary)}
              </CardContent>
            </Card>
          )}

          {introspectionResult.active_escalations &&
            introspectionResult.active_escalations.length > 0 && (
              <Card variant="outlined">
                <CardContent sx={{ p: 2.5 }}>
                <Typography sx={sectionTitleSx}>
                  Active Escalations
                </Typography>
                <Box sx={{ display: "grid", gap: 1 }}>
                  {introspectionResult.active_escalations.map((esc, i) => (
                    <StatusBadge key={i} status={esc} />
                  ))}
                </Box>
                </CardContent>
              </Card>
            )}

          {introspectionResult.active_constraints &&
            introspectionResult.active_constraints.length > 0 && (
              <Card variant="outlined">
                <CardContent sx={{ p: 2.5 }}>
                <Typography sx={sectionTitleSx}>
                  Active Constraints
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                  {introspectionResult.active_constraints.map((constraint) =>
                    renderConstraintBadge(constraint)
                  )}
                </Box>
                </CardContent>
              </Card>
            )}

          <JsonViewer
            title="Raw Introspection Data"
            data={introspectionResult}
          />
        </Box>
      )}

      {!introspectionLoading && !introspectionResult && !introspectionError && (
        <EmptyState title="No Actor Introspected" message="Enter an actor ID and click Inspect to view detailed behavior analysis." />
      )}
    </Box>
  );

  // Verdicts tab content
  const renderVerdictsTab = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Card variant="outlined">
        <CardContent sx={{ p: 2.5 }}>
          <Typography sx={sectionTitleSx}>
            Check Execution Verdict
          </Typography>

          <Box sx={{ display: "grid", gap: 2 }}>
            <TextField
              label="Actor ID"
              size="small"
              placeholder="e.g., agent-123"
              value={verdictActorId}
              onChange={(e) => setVerdictActorId(e.target.value)}
            />

            <FormControl size="small">
              <InputLabel id="verdict-operation-label">Operation</InputLabel>
              <Select
                labelId="verdict-operation-label"
                label="Operation"
                value={verdictOperation}
                onChange={(e) => setVerdictOperation(String(e.target.value))}
              >
                <MenuItem value="call_tool">Call Tool</MenuItem>
                <MenuItem value="read_resource">Read Resource</MenuItem>
                <MenuItem value="get_prompt">Get Prompt</MenuItem>
              </Select>
            </FormControl>

            <TextField
              label="Resource ID (optional)"
              size="small"
              placeholder="e.g., resource-456"
              value={verdictResourceId}
              onChange={(e) => setVerdictResourceId(e.target.value)}
            />

            <Button
              onClick={handleCheckVerdict}
              disabled={verdictLoading}
              variant="contained"
              sx={{
                bgcolor: "var(--app-accent)",
                color: "var(--app-accent-contrast)",
                "&:hover": { bgcolor: "var(--app-accent)" },
              }}
            >
              {verdictLoading ? "Checking..." : "Check Verdict"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {verdictError ? <Alert severity="error">{verdictError}</Alert> : null}

      {verdictLoading && <LoadingState message="Checking verdict..." />}

      {verdictResult && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Card variant="outlined">
            <CardContent sx={{ p: 3, textAlign: "center" }}>
              <Typography sx={{ ...sectionTitleSx, mb: 2 }}>
                Verdict
              </Typography>
              <Chip
                label={verdictResult.verdict}
                sx={{
                  px: 1,
                  py: 2,
                  fontWeight: 900,
                  ...(SEVERITY_COLORS[
                    verdictResult.verdict === "PROCEED"
                      ? "info"
                      : verdictResult.verdict === "THROTTLE"
                        ? "medium"
                        : verdictResult.verdict === "REQUIRE_CONFIRMATION"
                          ? "high"
                          : "critical"
                  ] as { bgcolor: string; color: string }),
                }}
              />
              <Typography sx={{ mt: 2, fontSize: 13, color: "var(--app-muted)" }}>
                {verdictResult.explanation}
              </Typography>
              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                Confidence: {(verdictResult.confidence * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>

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
        </Box>
      )}

      {!verdictLoading && !verdictResult && !verdictError && (
        <EmptyState title="No Verdict Checked" message="Fill in the form and click Check Verdict to evaluate execution permissions." />
      )}
    </Box>
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
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <TextField
        size="small"
        label="Filter by actor ID"
        placeholder="Filter by actor ID..."
        value={accountabilityFilter}
        onChange={(e) => setAccountabilityFilter(e.target.value)}
      />

      {filteredAccountability.length === 0 ? (
        <EmptyState title="No Log Entries" message="No accountability log entries to display." />
      ) : (
        <DataTable
          data={filteredAccountability}
          columns={[
            ...accountabilityColumns,
            {
              key: "details",
              header: "Details",
              render: (row) => (
                <Button
                  size="small"
                  variant="text"
                  onClick={(e) => {
                    e.stopPropagation();
                    const idx = filteredAccountability.indexOf(row);
                    setExpandedAccountabilityRow(expandedAccountabilityRow === idx ? null : idx);
                  }}
                  sx={{ color: "var(--app-muted)" }}
                >
                  {expandedAccountabilityRow === filteredAccountability.indexOf(row) ? "Hide" : "View"}
                </Button>
              ),
            } as Column<AccountabilityEntry>,
          ]}
          onRowClick={(row) => {
            const idx = filteredAccountability.indexOf(row);
            setExpandedAccountabilityRow(expandedAccountabilityRow === idx ? null : idx);
          }}
          emptyMessage="No accountability log entries to display."
          pageSize={8}
        />
      )}

      {expandedAccountabilityRow !== null && filteredAccountability[expandedAccountabilityRow] ? (
        <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
          <CardContent sx={{ p: 2.5 }}>
            <JsonViewer title="Full Entry" data={filteredAccountability[expandedAccountabilityRow]} />
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );

  const tabs = [
    { key: "introspection", label: "Introspection" },
    { key: "verdicts", label: "Verdicts" },
    { key: "accountability", label: "Accountability" },
  ];

  const accountabilityCount = initialAccountability.length;

  return (
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
              Reflexive workspace
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              Inspect actors before execution
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Check drift, execution verdicts, and accountability records without leaving the guardrail flow.
            </Typography>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            <Chip label={`${accountabilityCount} log entries`} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
            <Chip label={activeTab} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700 }} />
          </Box>
        </Box>

        <Divider />
        <Box sx={{ px: { xs: 1.5, md: 2 }, bgcolor: "var(--app-control-bg)" }}>
          <TabBar
            tabs={tabs}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </Box>
        <Divider />

        <Box sx={{ p: { xs: 2, md: 2.5 } }}>
          {activeTab === "introspection" && renderIntrospectionTab()}
          {activeTab === "verdicts" && renderVerdictsTab()}
          {activeTab === "accountability" && renderAccountabilityTab()}
        </Box>
        </CardContent>
    </Card>
  );
}

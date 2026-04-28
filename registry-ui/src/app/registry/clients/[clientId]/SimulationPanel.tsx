"use client";

import { useState } from "react";

import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  TextField,
  Typography,
} from "@mui/material";

import type {
  ClientSimulationResponse,
  ClientSimulationRequestPayload,
} from "@/lib/registryClient";

type Props = {
  slug: string;
};

const VERDICT_COLORS: Record<string, "success" | "warning" | "error"> = {
  allow: "success",
  review: "warning",
  deny: "error",
};

export function SimulationPanel({ slug }: Props) {
  const [action, setAction] = useState("call_tool");
  const [resourceId, setResourceId] = useState("");
  const [consentScope, setConsentScope] = useState("execute");
  const [consentSource, setConsentSource] = useState("");
  const [metricName, setMetricName] = useState("");
  const [metricValue, setMetricValue] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ClientSimulationResponse | null>(null);

  const canSubmit = !busy && action.trim() && resourceId.trim();

  async function runSimulation() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const payload: ClientSimulationRequestPayload = {
        action: action.trim(),
        resource_id: resourceId.trim(),
        consent_scope: consentScope.trim() || "execute",
      };
      if (consentSource.trim()) payload.consent_source_id = consentSource.trim();
      if (metricName.trim()) payload.metric_name = metricName.trim();
      if (metricValue.trim()) {
        const n = Number(metricValue);
        if (!Number.isFinite(n)) {
          setError("metric_value must be a number");
          setBusy(false);
          return;
        }
        payload.metric_value = n;
      }
      const res = await fetch(
        `/api/clients/${encodeURIComponent(slug)}/simulate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      const data = (await res.json().catch(() => ({}))) as ClientSimulationResponse;
      if (!res.ok) {
        setError(
          (typeof data.error === "string" && data.error) ||
            `Simulation failed (${res.status})`,
        );
        setResult(null);
        return;
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 1,
            flexWrap: "wrap",
          }}
        >
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Simulate request
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            Dry-runs through every plane — no records written.
          </Typography>
        </Box>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: {
              xs: "1fr",
              sm: "1fr 1fr",
            },
          }}
        >
          <TextField
            size="small"
            label="Action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="call_tool / read_resource / …"
            helperText="Logical action passed to the policy kernel"
          />
          <TextField
            size="small"
            label="Resource"
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
            placeholder="delete_user"
            helperText="Tool name or resource id"
          />
          <TextField
            size="small"
            label="Consent scope"
            value={consentScope}
            onChange={(e) => setConsentScope(e.target.value)}
            placeholder="execute"
            helperText="Scope checked on consent edges"
          />
          <TextField
            size="small"
            label="Consent source (optional)"
            value={consentSource}
            onChange={(e) => setConsentSource(e.target.value)}
            placeholder={resourceId || "node id"}
            helperText="Defaults to resource id"
          />
          <TextField
            size="small"
            label="Metric name (optional)"
            value={metricName}
            onChange={(e) => setMetricName(e.target.value)}
            placeholder="call_rate"
            helperText="Reflexive Core metric to score"
          />
          <TextField
            size="small"
            label="Metric value (optional)"
            value={metricValue}
            onChange={(e) => setMetricValue(e.target.value)}
            placeholder="3.2"
            type="number"
          />
        </Box>

        <Box sx={{ mt: 2, display: "flex", gap: 1, alignItems: "center" }}>
          <Button
            variant="contained"
            onClick={runSimulation}
            disabled={!canSubmit}
          >
            {busy ? "Simulating…" : "Run simulation"}
          </Button>
          {result ? (
            <Button variant="text" onClick={() => setResult(null)}>
              Clear result
            </Button>
          ) : null}
        </Box>

        {error ? (
          <Box
            sx={{
              mt: 2,
              p: 1.5,
              borderRadius: 2,
              border: "1px solid rgb(239, 68, 68)",
              bgcolor: "rgba(239, 68, 68, 0.08)",
            }}
          >
            <Typography
              variant="caption"
              sx={{ color: "rgb(254, 202, 202)", fontWeight: 600 }}
            >
              {error}
            </Typography>
          </Box>
        ) : null}

        {result ? <SimulationResult result={result} /> : null}
      </CardContent>
    </Card>
  );
}

function SimulationResult({ result }: { result: ClientSimulationResponse }) {
  const verdict = (result.verdict ?? "allow") as keyof typeof VERDICT_COLORS;
  const verdictColor = VERDICT_COLORS[verdict] ?? "success";
  const blockers = result.blockers ?? [];

  return (
    <Box sx={{ mt: 3, display: "grid", gap: 2 }}>
      <Box
        sx={{
          p: 2,
          borderRadius: 2,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
          display: "flex",
          alignItems: "center",
          gap: 2,
          flexWrap: "wrap",
        }}
      >
        <Chip
          label={`Verdict: ${verdict}`}
          color={verdictColor}
          sx={{ fontWeight: 800, textTransform: "uppercase" }}
        />
        {blockers.length > 0 ? (
          <Typography
            variant="caption"
            sx={{ color: "var(--app-muted)" }}
          >
            Blocked by:{" "}
            <Box component="span" sx={{ fontFamily: "monospace" }}>
              {blockers.map((b) => b.plane).join(", ")}
            </Box>
          </Typography>
        ) : (
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            All planes agreed.
          </Typography>
        )}
      </Box>

      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: {
            xs: "1fr",
            md: "repeat(2, 1fr)",
          },
        }}
      >
        <PlaneCard
          title="Policy"
          status={result.policy?.decision ?? "allow"}
          detail={result.policy?.reason}
          available={result.policy?.available}
          extra={
            result.policy?.policy_id
              ? `policy_id: ${result.policy.policy_id}`
              : undefined
          }
        />
        <PlaneCard
          title="Contracts"
          status={result.contracts?.covered ? "covered" : "not covered"}
          detail={result.contracts?.reason}
          available={result.contracts?.available}
          extra={
            result.contracts?.contracts && result.contracts.contracts.length > 0
              ? `${result.contracts.contracts.length} active contract(s)`
              : undefined
          }
        />
        <PlaneCard
          title="Consent"
          status={result.consent?.granted ? "granted" : "denied"}
          detail={result.consent?.reason}
          available={result.consent?.available}
          extra={
            result.consent?.path && result.consent.path.length > 0
              ? `path length: ${result.consent.path.length}`
              : undefined
          }
        />
        <PlaneCard
          title="Provenance"
          status={result.ledger?.would_record ? "would record" : "no record"}
          detail={result.ledger?.reason}
          available={result.ledger?.available}
          extra={
            result.ledger?.preview?.action
              ? `action: ${result.ledger.preview.action}`
              : undefined
          }
        />
        <PlaneCard
          title="Reflexive"
          status={
            result.reflexive?.evaluated
              ? `${result.reflexive?.severity ?? "info"} (${(
                  result.reflexive?.deviation_sigma ?? 0
                ).toFixed(2)}σ)`
              : "skipped"
          }
          detail={result.reflexive?.reason}
          available={result.reflexive?.available}
        />
      </Box>

      <Divider sx={{ borderColor: "var(--app-border)" }} />

      <Box>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 800,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Provenance preview (would record)
        </Typography>
        <Box
          sx={{
            mt: 1,
            p: 1.5,
            borderRadius: 2,
            border: "1px solid var(--app-border)",
            bgcolor: "var(--app-chrome-bg)",
            fontFamily: "monospace",
            fontSize: 11,
            color: "var(--app-fg)",
            overflow: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
          {JSON.stringify(result.ledger?.preview ?? {}, null, 2)}
        </Box>
      </Box>
    </Box>
  );
}

function PlaneCard({
  title,
  status,
  detail,
  available,
  extra,
}: {
  title: string;
  status: string;
  detail?: string;
  available?: boolean;
  extra?: string;
}) {
  const dim = available === false;
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        opacity: dim ? 0.7 : 1,
        display: "grid",
        gap: 0.5,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1,
        }}
      >
        <Typography
          sx={{
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {title}
        </Typography>
        {dim ? (
          <Chip
            label="disabled"
            size="small"
            variant="outlined"
            sx={{ fontSize: 10 }}
          />
        ) : null}
      </Box>
      <Typography
        sx={{ fontWeight: 800, color: "var(--app-fg)", fontSize: 14 }}
      >
        {status}
      </Typography>
      {extra ? (
        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
          {extra}
        </Typography>
      ) : null}
      {detail ? (
        <Typography
          variant="caption"
          sx={{ color: "var(--app-muted)", whiteSpace: "pre-wrap" }}
        >
          {detail}
        </Typography>
      ) : null}
    </Box>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Typography,
} from "@mui/material";

import type {
  ClientGovernanceResponse,
  RegistryClientSummary,
  RegistryClientTokenSummary,
} from "@/lib/registryClient";
import { RegistryPageHeader } from "@/components/security";

type Props = {
  client: RegistryClientSummary;
  tokens: RegistryClientTokenSummary[];
  governance: ClientGovernanceResponse | null;
};

const KIND_LABELS: Record<string, string> = {
  agent: "Agent",
  service: "Service",
  framework: "Framework",
  tooling: "Tooling",
  other: "Other",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

function formatTimestamp(ts: number | string | null | undefined): string {
  if (ts == null) return "—";
  if (typeof ts === "string") return ts;
  if (ts === 0) return "—";
  try {
    return new Date(ts * 1000).toISOString();
  } catch {
    return String(ts);
  }
}

export function ClientDetailView({ client, tokens, governance }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [issuedSecret, setIssuedSecret] =
    useState<{ name: string; secret: string } | null>(null);

  const isSuspended = client.status === "suspended";
  const slug = client.slug;

  const orderedTokens = useMemo(
    () =>
      [...tokens].sort(
        (a, b) =>
          (b.created_at ?? 0) - (a.created_at ?? 0),
      ),
    [tokens],
  );

  async function callApi(
    path: string,
    init: RequestInit,
  ): Promise<Record<string, unknown>> {
    const res = await fetch(path, init);
    const data = (await res.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    if (!res.ok) {
      const errMsg =
        typeof data.error === "string"
          ? (data.error as string)
          : `Request failed (${res.status})`;
      throw new Error(errMsg);
    }
    return data;
  }

  async function handleSuspend() {
    if (busy) return;
    const reason = window.prompt(
      "Reason for suspending? (optional, shown on the client page)",
      "",
    );
    if (reason === null) return;
    setBusy(true);
    setActionError(null);
    try {
      await callApi(`/api/clients/${encodeURIComponent(slug)}/suspend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to suspend");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnsuspend() {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await callApi(`/api/clients/${encodeURIComponent(slug)}/unsuspend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to unsuspend");
    } finally {
      setBusy(false);
    }
  }

  async function handleIssueToken() {
    if (busy) return;
    const name = window.prompt("Token name", "Default");
    if (!name || !name.trim()) return;
    setBusy(true);
    setActionError(null);
    try {
      const data = await callApi(
        `/api/clients/${encodeURIComponent(slug)}/tokens`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        },
      );
      const secret =
        typeof data.secret === "string" ? (data.secret as string) : "";
      setIssuedSecret({ name: name.trim(), secret });
      router.refresh();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to issue token",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRevokeToken(tokenId: string) {
    if (busy) return;
    if (
      !window.confirm(
        "Revoke this token? Existing requests using it will start failing immediately.",
      )
    ) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await callApi(
        `/api/clients/${encodeURIComponent(slug)}/tokens/${encodeURIComponent(
          tokenId,
        )}`,
        { method: "DELETE" },
      );
      router.refresh();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to revoke token",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Client profile"
        title={client.display_name || client.slug}
        description={`Slug: ${client.slug} · Owned by ${client.owner_publisher_id}`}
        actions={
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            <Chip
              label={kindLabel(client.kind)}
              size="small"
              sx={{
                bgcolor: "var(--app-control-active-bg)",
                color: "var(--app-fg)",
                fontWeight: 700,
              }}
            />
            <Chip
              label={isSuspended ? "Suspended" : "Active"}
              size="small"
              color={isSuspended ? "warning" : "success"}
              variant={isSuspended ? "filled" : "outlined"}
            />
          </Box>
        }
      />

      {actionError ? (
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            border: "1px solid rgb(239, 68, 68)",
            bgcolor: "rgba(239, 68, 68, 0.08)",
          }}
        >
          <Typography
            variant="caption"
            sx={{ color: "rgb(254, 202, 202)", fontWeight: 600 }}
          >
            {actionError}
          </Typography>
        </Box>
      ) : null}

      {issuedSecret ? (
        <Card variant="outlined" sx={{ borderColor: "rgb(245, 158, 11)" }}>
          <CardContent>
            <Typography
              variant="overline"
              sx={{
                color: "rgb(245, 158, 11)",
                fontWeight: 800,
                letterSpacing: "0.16em",
              }}
            >
              New token issued — save it now
            </Typography>
            <Typography variant="body2" sx={{ mt: 1, color: "var(--app-muted)" }}>
              Token name: <strong>{issuedSecret.name}</strong>. The plain
              secret is shown <strong>once</strong>; the registry only stores
              its hash going forward.
            </Typography>
            <Box
              sx={{
                mt: 1.5,
                p: 1.5,
                borderRadius: 2,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-chrome-bg)",
                fontFamily: "monospace",
                fontSize: 13,
                color: "var(--app-fg)",
                wordBreak: "break-all",
              }}
            >
              {issuedSecret.secret || "(no secret returned)"}
            </Box>
            <Box sx={{ mt: 1.5, display: "flex", gap: 1 }}>
              <Button
                size="small"
                variant="outlined"
                onClick={async () => {
                  if (issuedSecret.secret) {
                    await navigator.clipboard
                      .writeText(issuedSecret.secret)
                      .catch(() => {});
                  }
                }}
              >
                Copy secret
              </Button>
              <Button
                size="small"
                variant="text"
                onClick={() => setIssuedSecret(null)}
              >
                Dismiss
              </Button>
            </Box>
          </CardContent>
        </Card>
      ) : null}

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.4fr) minmax(0,1fr)" },
        }}
      >
        <Card variant="outlined">
          <CardContent>
            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              About
            </Typography>
            <Typography
              variant="body2"
              sx={{ mt: 1.5, color: "var(--app-muted)" }}
            >
              {client.description ||
                "This client has no description. Add one via the patch API or onboard wizard."}
            </Typography>

            <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />

            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Intended use
            </Typography>
            <Typography
              variant="body2"
              sx={{ mt: 1.5, color: "var(--app-muted)" }}
            >
              {client.intended_use || "—"}
            </Typography>

            {isSuspended && client.suspended_reason ? (
              <>
                <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />
                <Typography
                  sx={{
                    fontSize: 12,
                    fontWeight: 800,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "rgb(245, 158, 11)",
                  }}
                >
                  Suspension reason
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ mt: 1, color: "var(--app-fg)" }}
                >
                  {client.suspended_reason}
                </Typography>
              </>
            ) : null}
          </CardContent>
        </Card>

        <Card variant="outlined">
          <CardContent>
            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Snapshot
            </Typography>
            <Box component="dl" sx={{ mt: 1.5, display: "grid", gap: 1, m: 0 }}>
              <Row label="Slug" value={client.slug} mono />
              <Row label="Kind" value={kindLabel(client.kind)} />
              <Row
                label="Owner"
                value={
                  <Link
                    href={`/registry/publishers/${encodeURIComponent(
                      client.owner_publisher_id,
                    )}`}
                    style={{ color: "var(--app-accent)", fontWeight: 600 }}
                  >
                    {client.owner_publisher_id}
                  </Link>
                }
              />
              <Row
                label="Status"
                value={isSuspended ? "Suspended" : "Active"}
              />
              <Row label="Created" value={formatTimestamp(client.created_at)} />
              <Row label="Updated" value={formatTimestamp(client.updated_at)} />
            </Box>

            <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />

            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Manage
            </Typography>
            <Box sx={{ mt: 1.5, display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Button
                size="small"
                variant="contained"
                onClick={handleIssueToken}
                disabled={busy || isSuspended}
              >
                Issue token
              </Button>
              {isSuspended ? (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={handleUnsuspend}
                  disabled={busy}
                >
                  Unsuspend
                </Button>
              ) : (
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  onClick={handleSuspend}
                  disabled={busy}
                >
                  Suspend
                </Button>
              )}
            </Box>
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            API tokens · {orderedTokens.length}
          </Typography>
          {orderedTokens.length === 0 ? (
            <Typography
              variant="body2"
              sx={{ mt: 1.5, color: "var(--app-muted)" }}
            >
              No tokens yet. Issue one above to start authenticating requests.
            </Typography>
          ) : (
            <Box
              sx={{
                mt: 1.5,
                display: "grid",
                gap: 1.5,
                gridTemplateColumns: {
                  xs: "1fr",
                  md: "repeat(2, 1fr)",
                },
              }}
            >
              {orderedTokens.map((token) => (
                <Box
                  key={token.token_id}
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    border: "1px solid var(--app-border)",
                    bgcolor: "var(--app-control-bg)",
                    display: "grid",
                    gap: 0.75,
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 1,
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {token.name}
                    </Typography>
                    <Chip
                      size="small"
                      label={token.active ? "Active" : "Revoked"}
                      color={token.active ? "success" : "default"}
                      variant={token.active ? "outlined" : "filled"}
                    />
                  </Box>
                  <Typography
                    variant="caption"
                    sx={{ color: "var(--app-muted)", fontFamily: "monospace" }}
                  >
                    {token.secret_prefix}…
                  </Typography>
                  <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                    Created by {token.created_by} ·{" "}
                    {formatTimestamp(token.created_at)}
                  </Typography>
                  {token.last_used_at ? (
                    <Typography
                      variant="caption"
                      sx={{ color: "var(--app-muted)" }}
                    >
                      Last used: {formatTimestamp(token.last_used_at)}
                    </Typography>
                  ) : null}
                  {token.active ? (
                    <Box sx={{ mt: 0.5 }}>
                      <Button
                        size="small"
                        variant="text"
                        color="warning"
                        onClick={() => handleRevokeToken(token.token_id)}
                        disabled={busy}
                      >
                        Revoke
                      </Button>
                    </Box>
                  ) : null}
                </Box>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      <ClientGovernanceCard slug={client.slug} governance={governance} />

      <Box sx={{ pt: 1 }}>
        <Link href="/registry/clients" legacyBehavior passHref>
          <Box
            component="a"
            sx={{
              display: "inline-flex",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--app-muted)",
              textDecoration: "none",
              "&:hover": { color: "var(--app-fg)" },
            }}
          >
            ← Back to clients
          </Box>
        </Link>
      </Box>
    </Box>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "120px 1fr",
        alignItems: "baseline",
      }}
    >
      <Typography
        component="dt"
        variant="caption"
        sx={{
          color: "var(--app-muted)",
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontSize: 10,
        }}
      >
        {label}
      </Typography>
      <Typography
        component="dd"
        variant="body2"
        sx={{
          m: 0,
          color: "var(--app-fg)",
          fontFamily: mono
            ? "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
            : undefined,
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function ClientGovernanceCard({
  slug,
  governance,
}: {
  slug: string;
  governance: ClientGovernanceResponse | null;
}) {
  if (!governance || governance.error) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Governance roll-up
          </Typography>
          <Typography
            variant="body2"
            sx={{ mt: 1.5, color: "var(--app-muted)" }}
          >
            {governance?.error ??
              "Governance projection is unavailable for this client."}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const contracts = governance.contracts;
  const consent = governance.consent;
  const ledger = governance.ledger;
  const reflexive = governance.reflexive;

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
            Governance roll-up
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            actor_id ={" "}
            <Box component="span" sx={{ fontFamily: "monospace" }}>
              {slug}
            </Box>
          </Typography>
        </Box>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(2, 1fr)",
              md: "repeat(5, 1fr)",
            },
          }}
        >
          <PlaneTile
            title="Contracts"
            primary={String(contracts?.active_count ?? 0)}
            secondary="active"
          />
          <PlaneTile
            title="Consent"
            primary={String(consent?.outgoing_count ?? 0)}
            secondary={`outgoing · ${consent?.incoming_count ?? 0} incoming`}
          />
          <PlaneTile
            title="Ledger"
            primary={String(ledger?.record_count ?? 0)}
            secondary="records"
          />
          <PlaneTile
            title="Reflexive"
            primary={String(reflexive?.drift_event_count ?? 0)}
            secondary="drift events"
          />
          <PlaneTile
            title="Tokens"
            primary={String(governance.tokens?.active ?? 0)}
            secondary={`active · ${governance.tokens?.revoked ?? 0} revoked`}
          />
        </Box>

        {governance.policy?.note ? (
          <Typography
            variant="caption"
            sx={{ mt: 2, display: "block", color: "var(--app-muted)" }}
          >
            {governance.policy.note}
          </Typography>
        ) : null}

        {reflexive?.recent_drifts && reflexive.recent_drifts.length > 0 ? (
          <>
            <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Recent drift
            </Typography>
            <Box sx={{ mt: 1, display: "grid", gap: 0.75 }}>
              {reflexive.recent_drifts.slice(0, 5).map((drift, idx) => (
                <Box
                  key={drift.event_id ?? `drift-${idx}`}
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 1,
                    p: 1,
                    borderRadius: 1.5,
                    border: "1px solid var(--app-border)",
                    bgcolor: "var(--app-control-bg)",
                  }}
                >
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      {drift.drift_type ?? "drift"}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ display: "block", color: "var(--app-muted)" }}
                    >
                      {drift.timestamp ?? "—"}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={drift.severity ?? "info"}
                    color={
                      drift.severity === "critical" || drift.severity === "high"
                        ? "error"
                        : drift.severity === "medium"
                          ? "warning"
                          : "default"
                    }
                  />
                </Box>
              ))}
            </Box>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function PlaneTile({
  title,
  primary,
  secondary,
}: {
  title: string;
  primary: string;
  secondary: string;
}) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 0.5,
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
      <Typography variant="h6" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
        {primary}
      </Typography>
      <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
        {secondary}
      </Typography>
    </Box>
  );
}

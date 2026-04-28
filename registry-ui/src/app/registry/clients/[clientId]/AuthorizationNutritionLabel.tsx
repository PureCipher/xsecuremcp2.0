"use client";

import { useMemo } from "react";
import { Box, Card, CardContent, Chip, Typography } from "@mui/material";
import type {
  ClientGovernanceConsentRow,
  ClientGovernanceContractRow,
  ClientGovernanceResponse,
  RegistryClientSummary,
} from "@/lib/registryClient";

/**
 * Iter 14.34 — Authorization nutrition label.
 *
 * Symmetric to Iter 14.30 on the listing side. Where that component
 * shows what an MCP server is *allowed to do* (permissions, data
 * flows, resource access), this one shows what a client is
 * *allowed to call* — the inverse perspective for the same trust
 * decision.
 *
 * Three sections, each driven by a different governance plane:
 *
 *   1. Server access — from contracts.active_contracts. Which
 *      servers does this client currently hold an active contract
 *      with, and is that contract bounded (expires_at) or
 *      open-ended? Each row is one (server_id, status) pair.
 *
 *   2. Granted scopes — from consent.edges_from. Which scopes does
 *      the client have outgoing consent for (i.e., what kinds of
 *      operations is it authorized to perform), and which targets
 *      does that consent apply to? Delegatable consent gets an
 *      extra warning chip — being able to re-grant is a higher
 *      privilege than just holding the scope yourself.
 *
 *   3. Operational state — token totals, ledger record retention,
 *      and (if present) per-client rate-limit / ip-allowlist
 *      metadata. This is the operational shape of "what does this
 *      client get to do per unit time?".
 *
 * The card-level "headline severity" is computed from the worst
 * scope present across all outgoing consent edges, with a one-step
 * bump if any of those edges are delegatable. Read-only clients
 * stay calm, write/execute clients warn, admin/delegatable
 * combinations pop loud.
 *
 * The component is intentionally read-only — changing scopes or
 * contracts happens elsewhere (Consent Graph / Contract Broker
 * panels). Its job is to summarize the current authorization
 * surface in one place where the operator already lives.
 */

// ── Severity vocabulary ──────────────────────────────────────

type Severity = "low" | "elevated" | "high";

const SCOPE_SEVERITY: Record<string, Severity> = {
  // Pure read paths.
  read: "low",
  list: "low",
  view: "low",
  describe: "low",
  observe: "low",
  // State-changing but bounded.
  update: "elevated",
  modify: "elevated",
  mutate: "elevated",
  publish: "elevated",
  notify: "elevated",
  // Execution + destructive.
  execute: "high",
  call: "high",
  invoke: "high",
  write: "high",
  delete: "high",
  destroy: "high",
  // Privilege-controlling.
  admin: "high",
  manage: "high",
  grant: "high",
  revoke: "high",
};

function scopeSeverity(scope: string): Severity {
  const s = scope.trim().toLowerCase();
  if (s in SCOPE_SEVERITY) return SCOPE_SEVERITY[s];
  // Heuristic fallback — any unknown scope containing "write",
  // "exec", "admin", "delete" reads as high.
  if (/(write|exec|admin|delete|destroy|grant|revoke)/.test(s)) return "high";
  if (/(update|mutate|modify|publish)/.test(s)) return "elevated";
  return "low";
}

function bumpSeverity(s: Severity): Severity {
  if (s === "low") return "elevated";
  if (s === "elevated") return "high";
  return "high";
}

function severitySx(severity: Severity) {
  if (severity === "high") {
    return {
      bgcolor: "rgba(244, 63, 94, 0.10)",
      color: "#b91c1c",
      borderColor: "rgba(248, 113, 113, 0.4)",
    };
  }
  if (severity === "elevated") {
    return {
      bgcolor: "rgba(245, 158, 11, 0.12)",
      color: "#92400e",
      borderColor: "rgba(251, 191, 36, 0.4)",
    };
  }
  return {
    bgcolor: "var(--app-control-bg)",
    color: "var(--app-fg)",
    borderColor: "var(--app-border)",
  };
}

function severityLabel(severity: Severity): string {
  if (severity === "high") return "High";
  if (severity === "elevated") return "Elevated";
  return "Low";
}

// ── Metadata extraction ──────────────────────────────────────

type RateLimit = { value: number; window: string };

function extractRateLimit(metadata: unknown): RateLimit | null {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return null;
  }
  const meta = metadata as Record<string, unknown>;
  const raw =
    meta.rate_limit ?? meta.rateLimit ?? meta.requests_per_minute;
  if (raw == null) return null;
  // Numeric form: assume requests-per-minute.
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return { value: raw, window: "minute" };
  }
  // String form: e.g. "100/min" or "1000/hour".
  if (typeof raw === "string") {
    const m = raw.match(/^\s*(\d+)\s*(?:\/|\s+per\s+)\s*(\w+)\s*$/i);
    if (m) {
      const n = Number(m[1]);
      if (Number.isFinite(n)) return { value: n, window: m[2].toLowerCase() };
    }
    const n = Number(raw);
    if (Number.isFinite(n)) return { value: n, window: "minute" };
  }
  // Object form: { value: 100, window: "minute" }.
  if (typeof raw === "object" && raw !== null && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    const v = Number(obj.value ?? obj.limit ?? obj.requests);
    const w = String(obj.window ?? obj.per ?? obj.unit ?? "minute");
    if (Number.isFinite(v)) return { value: v, window: w.toLowerCase() };
  }
  return null;
}

function extractStringList(metadata: unknown, key: string): string[] {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return [];
  }
  const meta = metadata as Record<string, unknown>;
  const raw = meta[key];
  if (Array.isArray(raw)) {
    return raw
      .filter((item): item is string => typeof item === "string")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  return [];
}

// ── Component ────────────────────────────────────────────────

export function AuthorizationNutritionLabel({
  client,
  governance,
}: {
  client: RegistryClientSummary;
  governance: ClientGovernanceResponse | null;
}) {
  const tokens = governance?.tokens;
  const ledgerCount = governance?.ledger?.record_count ?? 0;

  // Read the source arrays inside the memoized blocks so we depend
  // on the stable reference from the governance payload rather than
  // fresh fallback `[]` literals on every render.
  const rawContracts = governance?.contracts?.active_contracts;
  const rawOutgoing = governance?.consent?.edges_from;

  // Aggregate distinct (server_id, status) pairs from contracts.
  const serverAccess = useMemo(() => {
    const contracts: ClientGovernanceContractRow[] = rawContracts ?? [];
    const seen = new Map<
      string,
      { server_id: string; status: string; expires: (string | null)[] }
    >();
    for (const c of contracts) {
      const key = `${c.server_id ?? "?"}::${c.status ?? "active"}`;
      const existing = seen.get(key);
      if (existing) {
        existing.expires.push(c.expires_at ?? null);
      } else {
        seen.set(key, {
          server_id: c.server_id ?? "?",
          status: c.status ?? "active",
          expires: [c.expires_at ?? null],
        });
      }
    }
    return Array.from(seen.values());
  }, [rawContracts]);

  // Group outgoing consent edges by scope. Each scope-row carries
  // the list of targets it covers and a delegatable flag (true if
  // *any* edge for that scope is delegatable).
  const scopeRows = useMemo(() => {
    const outgoing: ClientGovernanceConsentRow[] = rawOutgoing ?? [];
    type ScopeRow = {
      scope: string;
      severity: Severity;
      targets: string[];
      delegatable: boolean;
    };
    const map = new Map<string, ScopeRow>();
    for (const edge of outgoing) {
      const target = edge.target_id ?? "?";
      const isDelegatable = edge.delegatable === true;
      for (const rawScope of edge.scopes ?? []) {
        const scope = String(rawScope).trim();
        if (!scope) continue;
        const baseSev = scopeSeverity(scope);
        const sev = isDelegatable ? bumpSeverity(baseSev) : baseSev;
        const existing = map.get(scope);
        if (existing) {
          if (!existing.targets.includes(target)) {
            existing.targets.push(target);
          }
          if (isDelegatable) existing.delegatable = true;
          // Keep the worst severity we've seen for this scope.
          const order = { low: 0, elevated: 1, high: 2 };
          if (order[sev] > order[existing.severity]) {
            existing.severity = sev;
          }
        } else {
          map.set(scope, {
            scope,
            severity: sev,
            targets: [target],
            delegatable: isDelegatable,
          });
        }
      }
    }
    // Sort by severity desc then scope name.
    const order = { low: 2, elevated: 1, high: 0 };
    return Array.from(map.values()).sort((a, b) => {
      const cmp = order[a.severity] - order[b.severity];
      if (cmp !== 0) return cmp;
      return a.scope.localeCompare(b.scope);
    });
  }, [rawOutgoing]);

  const cardSeverity: Severity = useMemo(() => {
    if (scopeRows.some((r) => r.severity === "high")) return "high";
    if (scopeRows.some((r) => r.severity === "elevated")) return "elevated";
    return "low";
  }, [scopeRows]);

  const rateLimit = useMemo(
    () => extractRateLimit(client.metadata),
    [client.metadata],
  );
  const ipAllowlist = useMemo(
    () => extractStringList(client.metadata, "ip_allowlist"),
    [client.metadata],
  );

  const isSuspended = client.status === "suspended";

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 1,
            flexWrap: "wrap",
            mb: 1.5,
          }}
        >
          <Box>
            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Authorization label
            </Typography>
            <Typography
              sx={{ fontSize: 13, color: "var(--app-muted)", mt: 0.25 }}
            >
              What this client is allowed to call, derived from contracts and
              the consent graph.
            </Typography>
          </Box>
          <Chip
            size="small"
            label={`${severityLabel(cardSeverity)} privilege`}
            sx={{
              fontWeight: 700,
              fontSize: 11,
              height: 22,
              border: "1px solid",
              ...severitySx(cardSeverity),
            }}
          />
        </Box>

        {isSuspended ? (
          <Box
            sx={{
              p: 1.25,
              mb: 1.5,
              borderRadius: 2,
              border: "1px solid rgba(251, 191, 36, 0.4)",
              bgcolor: "rgba(245, 158, 11, 0.08)",
              fontSize: 12,
              color: "#92400e",
            }}
          >
            <strong>Suspended.</strong> The grants below remain on record but
            the registry will reject this client&apos;s requests until it is
            reinstated.
          </Box>
        ) : null}

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: {
              xs: "1fr",
              md: "minmax(0, 1fr) minmax(0, 1fr)",
            },
          }}
        >
          {/* SECTION 1 — Server access */}
          <SectionShell
            title="Server access"
            badge={
              <Chip
                size="small"
                label={`${serverAccess.length} server${serverAccess.length === 1 ? "" : "s"}`}
                sx={{
                  fontSize: 10.5,
                  height: 20,
                  bgcolor: "var(--app-control-bg)",
                  color: "var(--app-muted)",
                  border: "1px solid var(--app-border)",
                }}
              />
            }
          >
            {serverAccess.length === 0 ? (
              <EmptyText>
                No active contracts. The client is authenticated but has not
                been granted access to any server through the contract broker
                yet.
              </EmptyText>
            ) : (
              <Box sx={{ display: "grid", gap: 1 }}>
                {serverAccess.map((row, idx) => {
                  const expiresAt = row.expires.find((e) => e != null);
                  return (
                    <Box
                      key={`${row.server_id}-${row.status}-${idx}`}
                      sx={{
                        p: 1,
                        borderRadius: 1.5,
                        border: "1px solid var(--app-border)",
                        bgcolor: "var(--app-control-bg)",
                        display: "flex",
                        flexWrap: "wrap",
                        alignItems: "baseline",
                        gap: 1,
                      }}
                    >
                      <Box
                        component="code"
                        sx={{
                          fontFamily:
                            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                          fontSize: 12,
                          fontWeight: 700,
                          color: "var(--app-fg)",
                        }}
                      >
                        {row.server_id}
                      </Box>
                      <Chip
                        size="small"
                        label={row.status}
                        sx={{
                          fontSize: 10.5,
                          height: 20,
                          bgcolor: "var(--app-surface)",
                          color: "var(--app-muted)",
                          border: "1px solid var(--app-border)",
                        }}
                      />
                      {expiresAt ? (
                        <Typography
                          sx={{
                            fontSize: 11,
                            color: "var(--app-muted)",
                            ml: "auto",
                          }}
                        >
                          expires {expiresAt}
                        </Typography>
                      ) : (
                        <Typography
                          sx={{
                            fontSize: 11,
                            color: "var(--app-muted)",
                            ml: "auto",
                            fontStyle: "italic",
                          }}
                        >
                          open-ended
                        </Typography>
                      )}
                    </Box>
                  );
                })}
              </Box>
            )}
          </SectionShell>

          {/* SECTION 2 — Granted scopes */}
          <SectionShell
            title="Granted scopes"
            badge={
              <Chip
                size="small"
                label={`${scopeRows.length} scope${scopeRows.length === 1 ? "" : "s"}`}
                sx={{
                  fontSize: 10.5,
                  height: 20,
                  bgcolor: "var(--app-control-bg)",
                  color: "var(--app-muted)",
                  border: "1px solid var(--app-border)",
                }}
              />
            }
          >
            {scopeRows.length === 0 ? (
              <EmptyText>
                No outgoing consent grants. The client has no scope-bearing
                permissions in the consent graph yet.
              </EmptyText>
            ) : (
              <Box sx={{ display: "grid", gap: 1 }}>
                {scopeRows.map((row) => (
                  <Box
                    key={row.scope}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: "1px solid",
                      ...severitySx(row.severity),
                    }}
                  >
                    <Box
                      sx={{
                        display: "flex",
                        flexWrap: "wrap",
                        alignItems: "baseline",
                        gap: 1,
                        mb: 0.5,
                      }}
                    >
                      <Box
                        component="code"
                        sx={{
                          fontFamily:
                            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                          fontSize: 12,
                          fontWeight: 800,
                        }}
                      >
                        {row.scope}
                      </Box>
                      <Chip
                        size="small"
                        label={severityLabel(row.severity)}
                        sx={{
                          fontSize: 10,
                          height: 18,
                          bgcolor: "var(--app-surface)",
                          fontWeight: 700,
                        }}
                      />
                      {row.delegatable ? (
                        <Chip
                          size="small"
                          label="Delegatable"
                          sx={{
                            fontSize: 10,
                            height: 18,
                            fontWeight: 700,
                            bgcolor: "rgba(244, 63, 94, 0.10)",
                            color: "#b91c1c",
                            border: "1px solid rgba(248, 113, 113, 0.4)",
                          }}
                        />
                      ) : null}
                    </Box>
                    <Typography
                      sx={{
                        fontSize: 11,
                        color: "var(--app-muted)",
                        lineHeight: 1.5,
                      }}
                    >
                      Targets:{" "}
                      {row.targets
                        .slice(0, 4)
                        .map((t, i) => (i === 0 ? t : `· ${t}`))
                        .join(" ")}
                      {row.targets.length > 4
                        ? ` (+${row.targets.length - 4} more)`
                        : ""}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </SectionShell>
        </Box>

        {/* SECTION 3 — Operational state */}
        <Box
          sx={{
            mt: 2,
            p: 1.5,
            borderRadius: 2,
            border: "1px solid var(--app-border)",
            bgcolor: "var(--app-control-bg)",
            display: "grid",
            gap: 1,
            gridTemplateColumns: {
              xs: "repeat(2, 1fr)",
              sm: "repeat(4, 1fr)",
            },
          }}
        >
          <OpsTile
            label="Active tokens"
            value={String(tokens?.active ?? 0)}
            secondary={`${tokens?.revoked ?? 0} revoked`}
          />
          <OpsTile
            label="Audit records"
            value={ledgerCount.toLocaleString()}
            secondary="cumulative"
          />
          <OpsTile
            label="Rate limit"
            value={rateLimit ? `${rateLimit.value}` : "—"}
            secondary={rateLimit ? `per ${rateLimit.window}` : "no metadata"}
          />
          <OpsTile
            label="IP allowlist"
            value={ipAllowlist.length === 0 ? "—" : String(ipAllowlist.length)}
            secondary={
              ipAllowlist.length === 0
                ? "any source"
                : ipAllowlist.length === 1
                  ? "entry"
                  : "entries"
            }
          />
        </Box>

        <Typography
          sx={{
            mt: 1.5,
            fontSize: 11,
            color: "var(--app-muted)",
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          Severity heuristics: read/list/view scopes are low; mutate/publish
          scopes are elevated; execute/write/admin and delegatable consent are
          high. Rate limits and IP allowlists come from the client&apos;s
          metadata — populate them via the patch API to surface them here.
        </Typography>
      </CardContent>
    </Card>
  );
}

// ── Helpers ─────────────────────────────────────────────────

function SectionShell({
  title,
  badge,
  children,
}: {
  title: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 1,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          flexWrap: "wrap",
        }}
      >
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {title}
        </Typography>
        {badge}
      </Box>
      {children}
    </Box>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return (
    <Typography
      sx={{
        fontSize: 12,
        color: "var(--app-muted)",
        lineHeight: 1.55,
        fontStyle: "italic",
      }}
    >
      {children}
    </Typography>
  );
}

function OpsTile({
  label,
  value,
  secondary,
}: {
  label: string;
  value: string;
  secondary: string;
}) {
  return (
    <Box sx={{ display: "grid", gap: 0.25 }}>
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}
      >
        {value}
      </Typography>
      <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
        {secondary}
      </Typography>
    </Box>
  );
}

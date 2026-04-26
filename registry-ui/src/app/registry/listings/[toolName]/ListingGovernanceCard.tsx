"use client";

import Link from "next/link";

import {
  Box,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from "@mui/material";

import type { ListingGovernanceResponse } from "@/lib/registryClient";

// ── Listing Governance card ────────────────────────────────────────
//
// Iteration 7. Renders the per-listing rollup across all five
// governance planes + observability on the listing detail page,
// so a viewer browsing a single tool sees its operational posture
// without leaving for the publisher profile. Backed by
// ``GET /registry/tools/{tool_name}/governance``.
//
// The card has six sub-rows, one per plane. Each row carries:
// 1. A binding chip showing the plane's headline state for this
//    listing ("proxy allowlist · 3 tools" / "no contracts" /
//    "consent required" / "per-listing ledger" / "active" / "5
//    drift events").
// 2. A secondary chip with supporting context where useful (e.g.
//    "registry policy v1" alongside "inherited").
// 3. A link to the relevant /registry/* control-plane page.

type Tone = "neutral" | "positive" | "warning" | "danger";

type ChipSpec = {
  label: string;
  tone?: Tone;
  monospace?: boolean;
};

function chipSx(tone: Tone | undefined, monospace?: boolean) {
  const base = {
    fontWeight: 700,
    fontSize: 11,
    fontFamily: monospace ? "var(--font-geist-mono), monospace" : undefined,
  };
  switch (tone) {
    case "positive":
      return {
        ...base,
        bgcolor: "var(--app-control-active-bg)",
        color: "var(--app-fg)",
      };
    case "warning":
      return {
        ...base,
        bgcolor: "rgba(253, 230, 138, 0.4)",
        color: "#92400e",
      };
    case "danger":
      return {
        ...base,
        bgcolor: "rgba(244, 63, 94, 0.18)",
        color: "#b91c1c",
      };
    default:
      return {
        ...base,
        bgcolor: "var(--app-control-bg)",
        color: "var(--app-muted)",
        border: "1px solid var(--app-border)",
      };
  }
}

function ChipsRow({ chips }: { chips: ChipSpec[] }) {
  return (
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
      {chips.map((chip, idx) => (
        <Chip
          key={`${chip.label}-${idx}`}
          size="small"
          label={chip.label}
          sx={chipSx(chip.tone, chip.monospace)}
        />
      ))}
    </Stack>
  );
}

function PlaneRow({
  title,
  subtitle,
  chips,
  linkHref,
  linkLabel,
}: {
  title: string;
  subtitle?: string;
  chips: ChipSpec[];
  linkHref?: string;
  linkLabel?: string;
}) {
  return (
    <Box
      sx={{
        py: 1.25,
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "minmax(140px, 200px) 1fr auto" },
        alignItems: "center",
        gap: 1.25,
        borderTop: "1px solid var(--app-border)",
        "&:first-of-type": { borderTop: "none" },
      }}
    >
      <Box>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {title}
        </Typography>
        {subtitle ? (
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            {subtitle}
          </Typography>
        ) : null}
      </Box>

      <ChipsRow chips={chips} />

      {linkHref ? (
        <Link href={linkHref} className="hover:text-[--app-fg]" style={{ textDecoration: "none" }}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              color: "var(--app-muted)",
              whiteSpace: "nowrap",
            }}
          >
            {linkLabel ?? "Open →"}
          </Typography>
        </Link>
      ) : (
        <span />
      )}
    </Box>
  );
}

export function ListingGovernanceCard({
  governance,
  publicView = false,
}: {
  governance: ListingGovernanceResponse | null | undefined;
  publicView?: boolean;
}) {
  if (!governance || governance.error) {
    return null;
  }

  // ── Policy row ───────────────────────────────────────────────────
  const policyChips: ChipSpec[] = [];
  const policyBinding = governance.policy?.binding_source;
  if (policyBinding === "proxy_allowlist") {
    policyChips.push({
      label: `proxy allowlist · ${governance.policy?.policy_provider?.allowed_count ?? 0} tools`,
      tone: "positive",
    });
  } else {
    policyChips.push({ label: "inherits registry policy", tone: "neutral" });
  }
  const policyVersion = governance.policy?.registry_policy?.current_version;
  if (policyVersion != null) {
    policyChips.push({ label: `registry v${policyVersion}`, tone: "neutral" });
  }

  // ── Contracts row ────────────────────────────────────────────────
  const contractsChips: ChipSpec[] = [];
  if (!governance.contracts?.broker?.available) {
    contractsChips.push({ label: "broker disabled", tone: "neutral" });
  } else if (governance.contracts.binding_source === "agent_contracts") {
    contractsChips.push({
      label: `${governance.contracts.matching_contract_count} active contract${governance.contracts.matching_contract_count === 1 ? "" : "s"}`,
      tone: "positive",
    });
  } else {
    contractsChips.push({ label: "no agent contracts", tone: "neutral" });
  }

  // ── Consent row ──────────────────────────────────────────────────
  const consentChips: ChipSpec[] = [];
  if (governance.consent?.requires_consent) {
    consentChips.push({ label: "consent required", tone: "warning" });
  } else {
    consentChips.push({ label: "consent optional", tone: "neutral" });
  }
  if (governance.consent?.consent_graph?.available) {
    const grantCount = governance.consent.graph_grant_count;
    if (grantCount > 0) {
      consentChips.push({
        label: `${grantCount} grant${grantCount === 1 ? "" : "s"}`,
        tone: "positive",
      });
    } else {
      consentChips.push({ label: "no grants", tone: "neutral" });
    }
  } else {
    consentChips.push({ label: "graph disabled", tone: "neutral" });
  }

  // ── Ledger row ───────────────────────────────────────────────────
  const ledgerChips: ChipSpec[] = [];
  if (governance.ledger?.binding_source === "proxy_ledger") {
    ledgerChips.push({ label: "per-listing ledger", tone: "positive" });
  } else {
    ledgerChips.push({ label: "no listing ledger", tone: "neutral" });
  }
  if (governance.ledger?.ledger?.available) {
    const records = governance.ledger.central_record_count;
    if (records > 0) {
      ledgerChips.push({
        label: `${records} central record${records === 1 ? "" : "s"}`,
        tone: "positive",
      });
    }
  }

  // ── Overrides row ────────────────────────────────────────────────
  const overridesChips: ChipSpec[] = [];
  const overrideBinding = governance.overrides?.binding_source;
  const status = governance.overrides?.status ?? governance.status ?? "—";
  let statusTone: Tone = "neutral";
  if (status === "published") statusTone = "positive";
  else if (status === "pending_review") statusTone = "warning";
  else if (status === "suspended" || status === "rejected") statusTone = "danger";
  overridesChips.push({ label: status, tone: statusTone, monospace: true });
  if (overrideBinding === "moderation_pending") {
    overridesChips.push({ label: "awaiting moderator", tone: "warning" });
  }
  if (governance.overrides?.policy_override?.active) {
    overridesChips.push({
      label: `policy override · ${governance.overrides.policy_override.allowed_count} tools`,
      tone: "neutral",
    });
  }
  if ((governance.overrides?.yanked_versions?.length ?? 0) > 0) {
    overridesChips.push({
      label: `${governance.overrides!.yanked_versions.length} yanked`,
      tone: "danger",
    });
  }

  // ── Observability row ────────────────────────────────────────────
  const observabilityChips: ChipSpec[] = [];
  if (!governance.observability?.analyzer?.available) {
    observabilityChips.push({ label: "analyzer disabled", tone: "neutral" });
  } else if (governance.observability.binding_source === "monitored") {
    const peak = governance.observability.highest_severity ?? "info";
    let peakTone: Tone = "neutral";
    if (peak === "critical" || peak === "high") peakTone = "danger";
    else if (peak === "medium") peakTone = "warning";
    observabilityChips.push({
      label: `${governance.observability.drift_event_count} drift event${governance.observability.drift_event_count === 1 ? "" : "s"}`,
      tone: "neutral",
    });
    observabilityChips.push({ label: `peak: ${peak}`, tone: peakTone });
  } else {
    observabilityChips.push({ label: "no drift", tone: "neutral" });
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 1.5, mb: 1 }}>
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Operational governance
          </Typography>
          {publicView ? (
            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
              Public view — operator details redacted.
            </Typography>
          ) : null}
        </Box>

        <Box sx={{ mt: 1, mb: 0.5 }}>
          <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
            How this listing is bound across the registry&apos;s five governance planes plus behavioral observability. Each row links to the relevant control plane.
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          <PlaneRow
            title="Policy Kernel"
            chips={policyChips}
            linkHref={governance.links?.policy_kernel_url}
            linkLabel="Open Policy →"
          />
          <PlaneRow
            title="Contract Broker"
            chips={contractsChips}
            linkHref={governance.links?.contract_broker_url}
            linkLabel="Open Contracts →"
          />
          <PlaneRow
            title="Consent Graph"
            chips={consentChips}
            linkHref={governance.links?.consent_graph_url}
            linkLabel="Open Consent →"
          />
          <PlaneRow
            title="Provenance Ledger"
            subtitle={
              governance.ledger?.expected_ledger_id
                ? governance.ledger.expected_ledger_id
                : undefined
            }
            chips={ledgerChips}
            linkHref={governance.links?.provenance_ledger_url}
            linkLabel="Open Ledger →"
          />
          <PlaneRow
            title="Overrides"
            chips={overridesChips}
            linkHref={governance.links?.moderation_queue_url}
            linkLabel="Open queue →"
          />
          <PlaneRow
            title="Reflexive Core"
            chips={observabilityChips}
            linkHref={governance.links?.reflexive_core_url}
            linkLabel="Open Reflexive →"
          />
        </Box>

        {governance.publisher_id ? (
          <Box sx={{ mt: 2.5, pt: 1.5, borderTop: "1px solid var(--app-border)" }}>
            <Link
              href={
                governance.links?.publisher_url ??
                `/registry/publishers/${encodeURIComponent(governance.publisher_id)}`
              }
              style={{ textDecoration: "none" }}
              className="hover:text-[--app-fg]"
            >
              <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
                See {governance.publisher_id}&apos;s server profile →
              </Typography>
            </Link>
          </Box>
        ) : null}
      </CardContent>
    </Card>
  );
}

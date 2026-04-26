import Link from "next/link";

import {
  getPublisherProfile,
  getServerConsentGovernance,
  getServerContractGovernance,
  getServerLedgerGovernance,
  getServerObservability,
  getServerOverridesGovernance,
  getServerPolicyGovernance,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { ServerDetailTabs } from "./ServerDetailTabs";

import { Box, Card, CardContent, Chip, Typography } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

export default async function ServerDetailPage(props: {
  params: Promise<{ serverId: string }>;
}) {
  const { serverId } = await props.params;
  const decodedId = decodeURIComponent(serverId);

  // Fetch the publisher profile + every control-plane governance
  // view + the observability view in parallel. Each call powers a
  // panel on a tab; rolling them up here keeps page-load latency a
  // function of the slowest call rather than the sum.
  //
  // Iter1: policyGovernance     → Governance / Policy Kernel
  // Iter2: contractGovernance   → Governance / Contract Broker
  // Iter3: consentGovernance    → Governance / Consent Graph
  // Iter4: ledgerGovernance     → Governance / Provenance Ledger
  // Iter5: overridesGovernance  → Governance / Overrides
  // Iter6: observability        → Observability / Reflexive Core
  const [
    profile,
    policyGovernance,
    contractGovernance,
    consentGovernance,
    ledgerGovernance,
    overridesGovernance,
    observability,
  ] = await Promise.all([
    getPublisherProfile(decodedId),
    getServerPolicyGovernance(decodedId),
    getServerContractGovernance(decodedId),
    getServerConsentGovernance(decodedId),
    getServerLedgerGovernance(decodedId),
    getServerOverridesGovernance(decodedId),
    getServerObservability(decodedId),
  ]);
  if (!profile || profile.error) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Unable to load server
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            No server profile is available for{" "}
            <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
              {decodedId}
            </Box>
            .
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/servers" className="hover:text-[--app-fg]">
              <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-muted)" }}>
                ← Back to MCP servers
              </Typography>
            </Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  // Backend emits the summary fields flat at the top level (see
  // PublisherProfile.to_dict in src/purecipher/models.py).
  const summary: PublisherSummary = {
    publisher_id: profile.publisher_id ?? decodedId,
    display_name: profile.display_name,
    description: profile.description,
    listing_count: profile.listing_count,
    tool_count: profile.tool_count,
    verified_tool_count: profile.verified_tool_count,
    trust_score: profile.trust_score,
  };
  const listings: RegistryToolListing[] = profile.listings ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="MCP server profile"
        title={summary.display_name ?? summary.publisher_id}
        description={`${summary.publisher_id} · ${summary.tool_count ?? listings.length} tool${
          (summary.tool_count ?? listings.length) === 1 ? "" : "s"
        } in this registry`}
        actions={
          summary.trust_score?.overall != null ? (
            <Chip size="small" label={`Trust score ${summary.trust_score.overall.toFixed(1)}`} />
          ) : null
        }
      />

      <ServerDetailTabs
        serverId={decodedId}
        summary={summary}
        listings={listings}
        policyGovernance={policyGovernance}
        contractGovernance={contractGovernance}
        consentGovernance={consentGovernance}
        ledgerGovernance={ledgerGovernance}
        overridesGovernance={overridesGovernance}
        observability={observability}
      />

      <Box sx={{ pt: 1 }}>
        <Link href="/registry/servers" className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-muted)" }}>
            ← Back to MCP servers
          </Typography>
        </Link>
      </Box>
    </Box>
  );
}


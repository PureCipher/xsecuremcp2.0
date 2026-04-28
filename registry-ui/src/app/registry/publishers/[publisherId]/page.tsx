import Link from "next/link";
import { Box, Card, CardActionArea, CardContent, Chip, Typography } from "@mui/material";
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
import { CertificationBadge, RegistryPageHeader } from "@/components/security";
// Iter 14.26 — the governance tabs that used to live on
// ``/registry/servers/[serverId]`` now render below the publisher
// profile here. Same component, same data shapes — only the entry
// point moves.
import { ServerDetailTabs } from "../../servers/[serverId]/ServerDetailTabs";

export default async function PublisherProfilePage(props: { params: Promise<{ publisherId: string }> }) {
  const { publisherId } = await props.params;
  const decodedId = decodeURIComponent(publisherId);
  // Iter 14.26 — fetch the profile + every governance projection
  // in parallel so first paint includes both the profile cards and
  // the governance tabs. Each call powers one tab; rolling them up
  // here keeps page-load latency a function of the slowest call.
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

  if (!profile) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Publisher not found
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            No publisher profile is available for{" "}
            <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
              {decodedId}
            </Box>
            .
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/publishers"><Box sx={{ display: "inline-flex", fontSize: 11, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" }, }}>
                ← Back to all publishers
              </Box></Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (profile.error) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Unable to load publisher
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>{profile.error}</Typography>
          <Box sx={{ mt: 2 }}>
            <Link href="/registry/publishers"><Box sx={{ display: "inline-flex", fontSize: 11, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" }, }}>
                ← Back to all publishers
              </Box></Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  // Backend emits the summary fields flat at the top level (see
  // PublisherProfile.to_dict). Read them directly; fall back to a
  // minimal stub keyed by the URL slug when the response carries
  // no publisher_id (e.g., on certain edge errors).
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
        eyebrow="Publisher profile"
        title={summary.display_name ?? summary.publisher_id}
        description={`${summary.publisher_id} · ${
          summary.tool_count ?? summary.listing_count ?? 0
        } tool${
          (summary.tool_count ?? summary.listing_count ?? 0) === 1 ? "" : "s"
        } in this registry`}
        actions={
          summary.trust_score?.overall != null ? (
            <Chip size="small" label={`Trust score ${summary.trust_score.overall.toFixed(1)}`} />
          ) : null
        }
      />

      <Box component="section" sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.2fr) minmax(0,1fr)" } }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              About
            </Typography>
            <Typography sx={{ mt: 1.5, fontSize: 13, color: "var(--app-muted)" }}>
              {summary.description ?? "This publisher has not added a profile description yet."}
            </Typography>
          </CardContent>
        </Card>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Snapshot
            </Typography>
            <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
              <li>
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Tools:</Box>{" "}
                {summary.tool_count ?? summary.listing_count ?? listings.length}
              </li>
              {summary.verified_tool_count != null ? (
                <li>
                  <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Verified tools:</Box> {summary.verified_tool_count}
                </li>
              ) : null}
            </Box>
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Tools from this publisher
          </Typography>
          {listings.length === 0 ? (
            <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
              This publisher does not have any live verified tools yet.
            </Typography>
          ) : (
            <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              {listings.map((tool) => (
                <Card
                  key={tool.tool_name}
                  variant="outlined"
                  sx={{
                    borderRadius: 3,
                    borderColor: "var(--app-border)",
                    bgcolor: "var(--app-control-bg)",
                    boxShadow: "none",
                  }}
                >
                  <Link href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}><CardActionArea sx={{ borderRadius: 3 }}>
                      <CardContent sx={{ p: 2 }}>
                        <Box sx={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 1 }}>
                          <Box>
                            <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                              {tool.display_name ?? tool.tool_name}
                            </Typography>
                            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>{tool.tool_name}</Typography>
                          </Box>
                          <CertificationBadge level={tool.certification_level} />
                        </Box>
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          {tool.description ?? "No description provided."}
                        </Typography>
                      </CardContent>
                    </CardActionArea></Link>
                </Card>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Iter 14.26 — Governance + Observability tabs (formerly the
          MCP Servers detail page). Six tabs: Policy Kernel, Contract
          Broker, Consent Graph, Provenance Ledger, Overrides, Reflexive
          Core. Same component as before, same backend data — just
          rendered here so reviewers/admins don't have to navigate to
          a separate "MCP Servers" page to do publisher-scoped audit. */}
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
        <Link href="/registry/publishers"><Box sx={{ display: "inline-flex", fontSize: 11, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" }, }}>
            ← Back to all publishers
          </Box></Link>
      </Box>
    </Box>
  );
}

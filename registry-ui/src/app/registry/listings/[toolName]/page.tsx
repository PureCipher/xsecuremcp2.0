import { notFound } from "next/navigation";
import Link from "next/link";
import { Alert, AlertTitle, Box, Card, CardContent, Chip, Typography } from "@mui/material";
import {
  getInstallRecipes,
  getListingGovernance,
  getRegistrySession,
  getToolDetail,
  getToolVersions,
  verifyTool,
  type InstallRecipe,
  type RegistryToolListing,
  type ToolVersionItem,
} from "@/lib/registryClient";
import { AttestationBadge } from "@/components/security";
import { RecipeTabs } from "../RecipeTabs";
import { ListingGovernanceCard } from "./ListingGovernanceCard";
import { DeregisterListingButton } from "./DeregisterListingButton";
import { CertificationTierExplainer } from "./CertificationTierExplainer";
import { PerClientInstallSnippets } from "./PerClientInstallSnippets";
import { PermissionNutritionLabel } from "./PermissionNutritionLabel";
import { VersionHistory } from "./VersionHistory";

function isToolDetail(detail: unknown): detail is RegistryToolListing {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "tool_name" in detail &&
    typeof detail.tool_name === "string"
  );
}

export default async function ListingDetailPage(props: { params: Promise<{ toolName: string }> }) {
  const { toolName } = await props.params;
  const sessionPayload = await getRegistrySession();
  if (!sessionPayload?.session) {
    // layout will normally handle this, but keep it defensive
    return notFound();
  }

  const decodedName = decodeURIComponent(toolName);
  const [detail, install, verification, versionsPayload, governance] = await Promise.all([
    getToolDetail(decodedName),
    getInstallRecipes(decodedName),
    verifyTool(decodedName),
    getToolVersions(decodedName),
    getListingGovernance(decodedName),
  ]);

  if (!isToolDetail(detail)) {
    return notFound();
  }

  const tool = detail;

  const recipes: InstallRecipe[] = install?.recipes ?? [];
  const primaryRecipe = recipes[0];
  const secondaryRecipes = recipes.slice(1);

  const clientRecipes = secondaryRecipes.filter((r) =>
    ["mcp_client_http", "mcp_client_stdio"].includes(r.recipe_id),
  );
  const dockerRecipes = secondaryRecipes.filter((r) => r.recipe_id === "docker_compose");
  const verifyRecipes = secondaryRecipes.filter((r) => r.recipe_id === "verify_attestation");
  const otherRecipes = secondaryRecipes.filter(
    (r) =>
      !["mcp_client_http", "mcp_client_stdio", "docker_compose", "verify_attestation"].includes(
        r.recipe_id,
      ),
  );

  const versions: ToolVersionItem[] = versionsPayload?.versions ?? [];

  // Listings live in one of several status buckets — PUBLISHED is
  // the public default, PENDING_REVIEW means a moderator hasn't
  // approved it yet (typical for fresh curator submissions),
  // SUSPENDED means a moderator removed it. Surface non-public
  // status prominently so the curator knows the listing won't be
  // discoverable in the public catalog yet.
  const status = (tool.status ?? "").toLowerCase();
  const statusBanner =
    status === "pending_review" ? (
      <Alert severity="warning">
        <AlertTitle>Pending moderator review</AlertTitle>
        This listing has been submitted but isn&apos;t yet public. A
        reviewer will approve or reject it before it appears in the
        public catalog. You can keep this URL — once approved, the
        listing will be visible here automatically.
      </Alert>
    ) : status === "suspended" ? (
      <Alert severity="error">
        <AlertTitle>Suspended</AlertTitle>
        This listing has been removed from the public catalog by a
        moderator.
      </Alert>
    ) : status === "deregistered" ? (
      // Iter 14.11 — terminal removal. Loud red banner so anyone
      // who lands on the page knows the server is no longer in
      // service and proxy calls will be rejected with HTTP 410.
      <Alert severity="error">
        <AlertTitle>Deregistered</AlertTitle>
        This server has been deregistered by the registry admin and
        is no longer available. Calls to proxy-mode endpoints will
        be rejected with HTTP 410. Please remove or migrate any
        client integrations that still reference it.
      </Alert>
    ) : null;

  // Iter 14.11 — only registry admins may deregister, and only
  // listings that haven't already been removed.
  const canAdmin = sessionPayload.session.can_admin === true;
  const canDeregister =
    canAdmin &&
    new Set([
      "published",
      "suspended",
      "deprecated",
      "pending_review",
    ]).has(status);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {statusBanner}
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, color: "var(--app-muted)", fontSize: 12 }}>
            <Link href="/registry/app" className="hover:text-[--app-fg]">
              Tools
            </Link>
            <span>/</span>
            {tool.publisher_id ? (
              <>
                <Link
                  href={`/registry/publishers/${encodeURIComponent(tool.publisher_id)}`}
                  className="hover:text-[--app-fg]"
                >
                  {tool.publisher_id}
                </Link>
                <span>/</span>
              </>
            ) : null}
            <Box component="span" sx={{ color: "var(--app-fg)", fontWeight: 700 }}>
              {tool.display_name ?? tool.tool_name}
            </Box>
          </Box>

          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: "var(--app-fg)" }}>
            {tool.display_name ?? tool.tool_name}
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
            {tool.tool_name} · v{tool.version} · {tool.author}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <AttestationBadge
            kind={tool.attestation_kind}
            curatorId={tool.curator_id}
          />
          {tool.listing_id ? (
            <Link href={`/registry/publish?from=${encodeURIComponent(tool.listing_id)}`}>
              <Chip
                clickable
                label="Publish new version"
                sx={{
                  bgcolor: "var(--app-control-bg)",
                  border: "1px solid var(--app-accent)",
                  color: "var(--app-muted)",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.01em",
                  "&:hover": { bgcolor: "var(--app-control-active-bg)" },
                }}
              />
            </Link>
          ) : null}
          <CertificationTierExplainer level={tool.certification_level} size="md" />
          {canDeregister && tool.listing_id ? (
            <DeregisterListingButton
              listingId={tool.listing_id}
              toolName={tool.tool_name}
              displayName={tool.display_name ?? tool.tool_name}
              status={status}
            />
          ) : null}
        </Box>
      </Box>

      <Box component="section" sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.3fr) minmax(0,1fr)" } }}>
        <Card variant="outlined">
          <CardContent>
            <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Overview
            </Typography>
            <Typography sx={{ mt: 1.5, fontSize: 13, color: "var(--app-muted)" }}>
              {tool.description ?? "No description provided."}
            </Typography>

            {Array.isArray(tool.categories) && tool.categories.length > 0 ? (
              <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
                {tool.categories.map((cat: string) => (
                  <Chip
                    key={cat}
                    label={cat}
                    size="small"
                    sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-fg)" }}
                  />
                ))}
              </Box>
            ) : null}

            {/* Iter 14.30 — Old "Data flows" inline card was replaced
                by the PermissionNutritionLabel rendered as its own
                top-level section below (it covers data flows plus
                permissions and resource_access). */}
          </CardContent>
        </Card>

        <Card variant="outlined">
          <CardContent>
            <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Versions
            </Typography>
            {/* Iter 14.31 — Version history with manifest-change
                indicator. Each row tells the curator whether the
                signed manifest changed at that version (worth a
                fresh security review) or whether only metadata
                moved (no new permissions or data flows). */}
            <VersionHistory versions={versions} />
          </CardContent>
        </Card>
      </Box>

      {/* Iter 14.30 — Permission nutrition label. Renders the
          manifest's permissions / data_flows / resource_access as
          a structured Apple-style disclosure card. Sits ABOVE the
          install snippets so a curator sees what they're agreeing
          to before they paste config into their client. */}
      <PermissionNutritionLabel tool={tool} />

      {/* Iter 14.29 — Per-client install snippets. Generated from
          ``upstream_ref`` for the four most common MCP-aware
          clients. Sits above RecipeTabs because the curator's
          first action is "drop this into my client and use it";
          transport recipes (RecipeTabs) are the next layer down. */}
      <PerClientInstallSnippets tool={tool} />

      <RecipeTabs
        primaryRecipe={primaryRecipe ?? null}
        clientRecipes={clientRecipes}
        dockerRecipes={dockerRecipes}
        verifyRecipes={verifyRecipes}
        otherRecipes={otherRecipes}
      />

      <ListingGovernanceCard governance={governance} />

      {verification?.verification ? (
        <Card variant="outlined">
          <CardContent>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Verification
              </Typography>
              <Chip
                size="small"
                label={verification.verification.signature_valid ? "Signature valid" : "Signature invalid"}
                sx={{
                  bgcolor: verification.verification.signature_valid ? "var(--app-control-active-bg)" : "rgba(244, 63, 94, 0.18)",
                  color: verification.verification.signature_valid ? "var(--app-fg)" : "#b91c1c",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.01em",
                }}
              />
            </Box>
            <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
              Manifest match:{" "}
              <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                {verification.verification.manifest_match ? "yes" : "no"}
              </Box>
            </Typography>

            {Array.isArray(verification.verification.issues) && verification.verification.issues.length > 0 ? (
              <Box component="ul" sx={{ mt: 2, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                {verification.verification.issues.slice(0, 6).map((issue: string, idx: number) => (
                  <li key={idx}>{issue}</li>
                ))}
                {verification.verification.issues.length > 6 ? (
                  <li>
                    +{verification.verification.issues.length - 6} more issue
                    {verification.verification.issues.length - 6 === 1 ? "" : "s"}.
                  </li>
                ) : null}
              </Box>
            ) : (
              <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>
                No verification issues reported.
              </Typography>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Box sx={{ pt: 1 }}>
        <Link href="/registry/app" className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-muted)" }}>
            ← Back to all tools
          </Typography>
        </Link>
      </Box>
    </Box>
  );
}

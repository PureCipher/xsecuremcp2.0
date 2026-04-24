import Link from "next/link";
import { notFound } from "next/navigation";

import { Box, Card, CardContent, Chip, Typography } from "@mui/material";

import {
  getInstallRecipes,
  getToolDetail,
  verifyTool,
  type InstallRecipe,
  type RegistryDataFlow,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { CertificationBadge } from "@/components/security";
import { RecipeTabs } from "@/app/registry/listings/RecipeTabs";

function isToolDetail(detail: unknown): detail is RegistryToolListing {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "tool_name" in detail &&
    typeof (detail as any).tool_name === "string"
  );
}

export default async function PublicListingDetailPage(props: {
  params: Promise<{ toolName: string }>;
}) {
  const { toolName } = await props.params;
  const decodedName = decodeURIComponent(toolName);

  const [detail, install, verification] = await Promise.all([
    getToolDetail(decodedName),
    getInstallRecipes(decodedName),
    verifyTool(decodedName),
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

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, color: "var(--app-muted)", fontSize: 12 }}>
            <Link href="/public/tools" legacyBehavior passHref>
              <Box component="a" sx={{ textDecoration: "none", color: "var(--app-muted)", "&:hover": { color: "var(--app-fg)" } }}>
                Tools
              </Box>
            </Link>
            <span>/</span>
            {tool.publisher_id ? (
              <>
                <Link href={`/public/publishers/${encodeURIComponent(tool.publisher_id)}`} legacyBehavior passHref>
                  <Box component="a" sx={{ textDecoration: "none", color: "var(--app-muted)", "&:hover": { color: "var(--app-fg)" } }}>
                    {tool.publisher_id}
                  </Box>
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
        <CertificationBadge level={tool.certification_level} size="md" />
      </Box>

      <Box component="section" sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.3fr) minmax(0,1fr)" } }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Overview
            </Typography>
            <Typography sx={{ mt: 1.5, fontSize: 13, color: "var(--app-muted)" }}>
              {tool.description ?? "No description provided."}
            </Typography>

            {Array.isArray(tool.categories) && tool.categories.length > 0 ? (
              <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
                {tool.categories.map((cat: string) => (
                  <Chip key={cat} label={cat} size="small" sx={{ borderRadius: 999, bgcolor: "var(--app-control-bg)", color: "var(--app-fg)" }} />
                ))}
              </Box>
            ) : null}

            {tool.manifest ? (
              <Card variant="outlined" sx={{ mt: 2, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Data flows</Typography>
                  {Array.isArray(tool.manifest.data_flows) && tool.manifest.data_flows.length > 0 ? (
                    <Box component="ul" sx={{ mt: 1, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                      {tool.manifest.data_flows.map((flow: RegistryDataFlow, idx: number) => (
                        <li key={idx}>
                          <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                            {flow.classification ?? "internal"}:
                          </Box>{" "}
                          {flow.source} → {flow.destination}
                          {flow.description ? ` — ${flow.description}` : null}
                        </li>
                      ))}
                    </Box>
                  ) : (
                    <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                      No explicit data_flows were declared in the manifest.
                    </Typography>
                  )}
                </CardContent>
              </Card>
            ) : null}
          </CardContent>
        </Card>
      </Box>

      <RecipeTabs
        primaryRecipe={primaryRecipe ?? null}
        clientRecipes={clientRecipes}
        dockerRecipes={dockerRecipes}
        verifyRecipes={verifyRecipes}
        otherRecipes={otherRecipes}
      />

      {verification ? (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Verification
              </Typography>
              <Chip
                size="small"
                label={verification.verification?.signature_valid ? "Signature valid" : "Signature invalid"}
                sx={{
                  borderRadius: 999,
                  bgcolor: verification.verification?.signature_valid ? "var(--app-control-active-bg)" : "rgba(244, 63, 94, 0.18)",
                  color: verification.verification?.signature_valid ? "var(--app-fg)" : "rgb(254, 205, 211)",
                  fontSize: 10,
                  fontWeight: 800,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                }}
              />
            </Box>
            <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
              Manifest match:{" "}
              <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                {verification.verification?.manifest_match ? "yes" : "no"}
              </Box>
            </Typography>
            {Array.isArray(verification.verification?.issues) && verification.verification.issues.length > 0 ? (
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
              <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>No verification issues reported.</Typography>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Box sx={{ pt: 1 }}>
        <Link href="/public/tools" legacyBehavior passHref>
          <Box component="a" sx={{ fontSize: 12, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" } }}>
            ← Back to all tools
          </Box>
        </Link>
      </Box>
    </Box>
  );
}


import { notFound } from "next/navigation";
import Link from "next/link";
import {
  getInstallRecipes,
  getRegistrySession,
  getToolDetail,
  verifyTool,
  type InstallRecipe,
  type RegistryDataFlow,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { CertificationBadge } from "@/components/security";
import { RecipeTabs } from "../RecipeTabs";

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
    <div className="flex flex-col gap-6">
        <div className="flex items-baseline justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-[--app-muted]">
              <Link
                href="/registry/app"
                className="hover:text-[--app-fg]"
              >
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
              <span className="text-[--app-fg]">
                {tool.display_name ?? tool.tool_name}
              </span>
            </div>
            <h1 className="text-2xl font-semibold text-[--app-fg]">
              {tool.display_name ?? tool.tool_name}
            </h1>
            <p className="mt-1 text-[11px] text-[--app-muted]">
              {tool.tool_name} · v{tool.version} · {tool.author}
            </p>
          </div>
          <CertificationBadge level={tool.certification_level} size="md" />
        </div>

        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <div className="space-y-3 rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Overview
            </h2>
            <p className="text-[13px] leading-relaxed text-[--app-muted]">
              {tool.description ?? "No description provided."}
            </p>
            <div className="flex flex-wrap gap-2 pt-1 text-[10px] text-[--app-muted]">
              {Array.isArray(tool.categories)
                ? tool.categories.map((cat: string) => (
                    <span
                      key={cat}
                      className="rounded-full bg-[--app-control-bg] px-2 py-0.5 text-[10px] font-medium text-[--app-fg]"
                    >
                      {cat}
                    </span>
                  ))
                : null}
            </div>
            {tool.manifest ? (
              <div className="mt-3 space-y-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-3 text-[11px] ring-1 ring-[--app-surface-ring]">
                <p className="font-semibold text-[--app-fg]">Data flows</p>
                {Array.isArray(tool.manifest.data_flows) &&
                tool.manifest.data_flows.length > 0 ? (
                  <ul className="space-y-1 text-[10px] text-[--app-muted]">
                    {tool.manifest.data_flows.map((flow: RegistryDataFlow, idx: number) => (
                      <li key={idx}>
                        <span className="font-semibold">
                          {flow.classification ?? "internal"}:
                        </span>{" "}
                        {flow.source} → {flow.destination}
                        {flow.description ? ` — ${flow.description}` : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[10px] text-[--app-muted]">
                    No explicit data_flows were declared in the manifest.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        </section>

        <RecipeTabs
          primaryRecipe={primaryRecipe ?? null}
          clientRecipes={clientRecipes}
          dockerRecipes={dockerRecipes}
          verifyRecipes={verifyRecipes}
          otherRecipes={otherRecipes}
        />

        {verification ? (
          <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                Verification
              </h2>
              <span
                className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ring-1 ${
                  verification.verification?.signature_valid
                    ? "bg-[--app-control-active-bg] text-[--app-fg] ring-[--app-accent]"
                    : "bg-rose-500/15 text-rose-100 ring-rose-400/25"
                }`}
              >
                {verification.verification?.signature_valid ? "Signature valid" : "Signature invalid"}
              </span>
            </div>
            <p className="mt-2 text-[11px] text-[--app-muted]">
              Manifest match:{" "}
              <span className="font-semibold">
                {verification.verification?.manifest_match ? "yes" : "no"}
              </span>
            </p>
            {Array.isArray(verification.verification?.issues) &&
            verification.verification.issues.length > 0 ? (
              <ul className="mt-3 space-y-1 text-[11px] text-[--app-muted]">
                {verification.verification.issues.slice(0, 6).map((issue: string, idx: number) => (
                  <li key={idx} className="text-[10px] leading-snug">
                    • {issue}
                  </li>
                ))}
                {verification.verification.issues.length > 6 ? (
                  <li className="text-[10px] text-[--app-muted]">
                    +{verification.verification.issues.length - 6} more issue
                    {verification.verification.issues.length - 6 === 1 ? "" : "s"}.
                  </li>
                ) : null}
              </ul>
            ) : (
              <p className="mt-3 text-[11px] text-[--app-muted]">No verification issues reported.</p>
            )}
          </section>
        ) : null}

        <div className="pt-2">
          <Link
            href="/registry/app"
            className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
          >
            ← Back to all tools
          </Link>
        </div>
    </div>
  );
}

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
    <main className="px-4 py-8 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex items-baseline justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-emerald-200/90">
              <Link
                href="/registry/app"
                className="hover:text-emerald-100"
              >
                Tools
              </Link>
              <span>/</span>
              {tool.publisher_id ? (
                <>
                  <Link
                    href={`/registry/publishers/${encodeURIComponent(tool.publisher_id)}`}
                    className="hover:text-emerald-100"
                  >
                    {tool.publisher_id}
                  </Link>
                  <span>/</span>
                </>
              ) : null}
              <span className="text-emerald-100">
                {tool.display_name ?? tool.tool_name}
              </span>
            </div>
            <h1 className="text-2xl font-semibold text-emerald-50">
              {tool.display_name ?? tool.tool_name}
            </h1>
            <p className="mt-1 text-[11px] text-emerald-200/90">
              {tool.tool_name} · v{tool.version} · {tool.author}
            </p>
          </div>
          <span className="rounded-full bg-emerald-900/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
            {tool.certification_level?.toUpperCase?.() ?? "UNRATED"}
          </span>
        </div>

        <section className="grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="space-y-3 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Overview
            </h2>
            <p className="text-[13px] leading-relaxed text-emerald-100/90">
              {tool.description ?? "No description provided."}
            </p>
            <div className="flex flex-wrap gap-2 pt-1 text-[10px] text-emerald-200/90">
              {Array.isArray(tool.categories)
                ? tool.categories.map((cat: string) => (
                    <span
                      key={cat}
                      className="rounded-full bg-emerald-950/70 px-2 py-0.5 text-[10px] font-medium text-emerald-100"
                    >
                      {cat}
                    </span>
                  ))
                : null}
            </div>
            {tool.manifest ? (
              <div className="mt-3 space-y-2 rounded-2xl bg-emerald-950/70 p-3 text-[11px] ring-1 ring-emerald-700/70">
                <p className="font-semibold text-emerald-50">Data flows</p>
                {Array.isArray(tool.manifest.data_flows) &&
                tool.manifest.data_flows.length > 0 ? (
                  <ul className="space-y-1 text-[10px] text-emerald-200/90">
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
                  <p className="text-[10px] text-emerald-200/90">
                    No explicit data_flows were declared in the manifest.
                  </p>
                )}
              </div>
            ) : null}
          </div>

          <div className="space-y-3 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Start here
            </h2>
            {primaryRecipe ? (
              <div className="space-y-2">
                <p className="text-[12px] text-emerald-100/90">{primaryRecipe.title}</p>
                <pre className="max-h-56 overflow-auto rounded-2xl bg-emerald-950/90 p-3 text-[11px] leading-relaxed text-emerald-50">
                  {primaryRecipe.content}
                </pre>
              </div>
            ) : (
              <p className="text-[12px] text-emerald-100/80">
                This listing doesn&apos;t expose runtime recipes yet.
              </p>
            )}
            {verification ? (
              <div className="mt-3 space-y-1 rounded-2xl bg-emerald-950/70 p-3 text-[11px] ring-1 ring-emerald-700/70">
                <p className="font-semibold text-emerald-50">Verification</p>
                <p className="text-emerald-100/90">
                  Signature:{" "}
                  <span className="font-semibold">
                    {verification.verification?.signature_valid ? "valid" : "invalid"}
                  </span>
                  {" · "}
                  Manifest match:{" "}
                  <span className="font-semibold">
                    {verification.verification?.manifest_match ? "yes" : "no"}
                  </span>
                </p>
                {Array.isArray(verification.verification?.issues) &&
                verification.verification.issues.length > 0 ? (
                  <ul className="mt-1 space-y-1 text-emerald-200/90">
                    {verification.verification.issues.slice(0, 3).map((issue: string, idx: number) => (
                      <li key={idx} className="text-[10px] leading-snug">
                        • {issue}
                      </li>
                    ))}
                    {verification.verification.issues.length > 3 ? (
                      <li className="text-[10px] text-emerald-300/90">
                        +{verification.verification.issues.length - 3} more issue
                        {verification.verification.issues.length - 3 === 1 ? "" : "s"}.
                      </li>
                    ) : null}
                  </ul>
                ) : (
                  <p className="text-[10px] text-emerald-200/90">
                    No verification issues were reported for this listing.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        </section>

        {secondaryRecipes.length > 0 ? (
          <section className="space-y-4">
            {clientRecipes.length > 0 && (
              <RecipeGroup title="Client setup" recipes={clientRecipes} />
            )}
            {dockerRecipes.length > 0 && (
              <RecipeGroup title="Docker & runtime" recipes={dockerRecipes} />
            )}
            {verifyRecipes.length > 0 && (
              <RecipeGroup title="Verification" recipes={verifyRecipes} />
            )}
            {otherRecipes.length > 0 && (
              <RecipeGroup title="Other recipes" recipes={otherRecipes} />
            )}
          </section>
        ) : null}

        <div className="pt-2">
          <Link
            href="/registry/app"
            className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100"
          >
            ← Back to all tools
          </Link>
        </div>
      </div>
    </main>
  );
}

function RecipeGroup({ title, recipes }: { title: string; recipes: InstallRecipe[] }) {
  return (
    <div className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
        {title}
      </h2>
      <div className="grid gap-3 md:grid-cols-3">
        {recipes.map((recipe) => (
          <article
            key={recipe.recipe_id}
            className="flex flex-col gap-2 rounded-2xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60"
          >
            <h3 className="text-[12px] font-semibold text-emerald-50">{recipe.title}</h3>
            <pre className="max-h-40 overflow-auto rounded-xl bg-emerald-950/90 p-2 text-[11px] leading-relaxed text-emerald-50">
              {recipe.content}
            </pre>
          </article>
        ))}
      </div>
    </div>
  );
}

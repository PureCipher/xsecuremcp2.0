import { redirect } from "next/navigation";

import { getRegistrySession } from "@/lib/registryClient";
import { LoginFormGate } from "./LoginFormGate";

export default async function LoginPage() {
  const sessionPayload = await getRegistrySession();

  if (sessionPayload?.auth_enabled === false) {
    redirect("/registry/app");
  }

  if (sessionPayload?.session != null) {
    const role = sessionPayload.session.role ?? "";
    if (role === "publisher") redirect("/registry/publish/mine");
    if (role === "reviewer") redirect("/registry/review");
    redirect("/registry/app");
  }

  const backendUnreachable = sessionPayload == null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[--app-bg] px-4 py-10 text-sm text-[--app-fg]">
      <div className="grid w-full max-w-5xl gap-10 rounded-3xl border border-[--app-border] bg-[--app-surface] p-8 ring-1 ring-[--app-surface-ring] backdrop-blur-lg md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:p-10">
        <section className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-[--app-border] bg-[--app-control-bg] px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-[--app-muted] ring-1 ring-[--app-surface-ring]">
            <span>PureCipher</span>
            <span className="h-1 w-1 rounded-full bg-[--app-accent]" />
            <span>Secured MCP Registry</span>
          </div>
          <div className="space-y-3">
            <h1 className="text-balance text-3xl font-semibold leading-tight text-[--app-fg] md:text-4xl">
              Find a tool you can trust.
            </h1>
            <p className="max-w-xl text-sm leading-relaxed text-[--app-muted]">
              Browse a vetted catalog of MCP tools, understand what each one can access, and share your own
              listings with clear security context.
            </p>
          </div>
          <dl className="grid gap-4 text-xs text-[--app-muted] sm:grid-cols-3">
            <div className="space-y-1 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <dt className="font-medium text-[--app-fg]">Verified listings</dt>
              <dd>Attested manifests and certification levels for every published tool.</dd>
            </div>
            <div className="space-y-1 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <dt className="font-medium text-[--app-fg]">Role-aware access</dt>
              <dd>Viewer, publisher, reviewer, and admin roles mapped to real workflows.</dd>
            </div>
            <div className="space-y-1 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <dt className="font-medium text-[--app-fg]">Copy-ready setup</dt>
              <dd>Client, Docker, and CI snippets generated from runtime metadata.</dd>
            </div>
          </dl>
        </section>

        <section className="flex flex-col items-center justify-center gap-4">
          {backendUnreachable ? (
            <p
              className="max-w-xs rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs text-amber-100"
              role="status"
            >
              Cannot reach the registry API at{" "}
              <span className="font-mono text-[11px]">
                {process.env.REGISTRY_BACKEND_URL ?? "http://localhost:8000"}
              </span>
              . Start the Python registry (for example{" "}
              <span className="font-mono text-[11px]">uv run python examples/securemcp/purecipher_registry.py</span>
              ) then refresh.
            </p>
          ) : null}
          <LoginFormGate />
        </section>
      </div>
    </div>
  );
}


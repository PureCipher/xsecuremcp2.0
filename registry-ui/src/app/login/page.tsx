import { redirect } from "next/navigation";
import { Typography } from "@mui/material";

import { getRegistrySession, getRegistryUserPreferences } from "@/lib/registryClient";
import { LoginFormGate } from "./LoginFormGate";

export default async function LoginPage() {
  const sessionPayload = await getRegistrySession();

  if (sessionPayload?.auth_enabled === false) {
    redirect("/registry/app");
  }

  if (sessionPayload?.session != null) {
    const preferencesPayload = await getRegistryUserPreferences();
    const preferredLanding = normalizeRegistryLanding(
      preferencesPayload?.preferences?.workspace?.defaultLandingPage,
    );
    if (preferredLanding) redirect(preferredLanding);

    const role = sessionPayload.session.role ?? "";
    if (role === "publisher") redirect("/registry/publish/mine");
    if (role === "reviewer") redirect("/registry/review");
    redirect("/registry/app");
  }

  const backendUnreachable = sessionPayload == null;
  const bootstrapRequired = sessionPayload?.bootstrap_required === true;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[--app-bg] px-4 py-10 text-sm text-[--app-fg]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(37,99,235,0.10),transparent_34%),radial-gradient(circle_at_18%_18%,rgba(14,165,233,0.12),transparent_30%),radial-gradient(circle_at_85%_15%,rgba(15,23,42,0.08),transparent_34%)]" />
      <div className="pointer-events-none absolute left-10 top-10 h-28 w-28 border border-[--app-border] opacity-60" />
      <div className="pointer-events-none absolute bottom-12 right-12 h-40 w-40 border border-[--app-border] opacity-50" />

      <div className="relative grid w-full max-w-6xl overflow-hidden border border-[--app-border] bg-[--app-surface]/95 shadow-[0_28px_90px_rgba(15,23,42,0.12)] ring-1 ring-[--app-surface-ring] backdrop-blur-xl lg:grid-cols-[minmax(0,1.1fr)_440px]">
        <section className="relative min-h-[560px] overflow-hidden border-b border-[--app-border] p-7 sm:p-10 lg:border-b-0 lg:border-r lg:p-12">
          <div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,var(--app-accent),rgba(14,165,233,0.45),transparent)]" />
          <div className="inline-flex items-center gap-2 border border-[--app-border] bg-[--app-control-bg] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] text-[--app-muted] ring-1 ring-[--app-surface-ring]">
            <span>PureCipher</span>
            <span className="h-1 w-1 bg-[--app-accent]" />
            <span>Secured MCP Registry</span>
          </div>

          <div className="mt-10 max-w-2xl space-y-5">
            <Typography
              variant="h3"
              sx={{
                color: "var(--app-fg)",
                fontWeight: 850,
                letterSpacing: "-0.055em",
                lineHeight: 0.96,
              }}
            >
              {bootstrapRequired ? "Create your first admin." : "Find a tool you can trust."}
            </Typography>
            <Typography variant="body1" sx={{ maxWidth: "42rem", color: "var(--app-muted)", fontSize: 17, lineHeight: 1.75 }}>
              {bootstrapRequired
                ? "No registry accounts exist yet. Create the first admin account to finish setup."
                : "Browse a vetted catalog of MCP tools, understand what each one can access, and share your own listings with clear security context."}
            </Typography>
          </div>

          <dl className="mt-10 grid gap-3 text-xs text-[--app-muted] sm:grid-cols-3">
            <div className="border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <Typography component="dt" variant="body2" sx={{ fontWeight: 850, color: "var(--app-fg)" }}>
                Verified listings
              </Typography>
              <Typography component="dd" variant="body2" sx={{ mt: 1, color: "var(--app-muted)", lineHeight: 1.65 }}>
                Attested manifests and certification levels for every published tool.
              </Typography>
            </div>
            <div className="border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <Typography component="dt" variant="body2" sx={{ fontWeight: 850, color: "var(--app-fg)" }}>
                Role-aware access
              </Typography>
              <Typography component="dd" variant="body2" sx={{ mt: 1, color: "var(--app-muted)", lineHeight: 1.65 }}>
                Viewer, publisher, reviewer, and admin roles mapped to real workflows.
              </Typography>
            </div>
            <div className="border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <Typography component="dt" variant="body2" sx={{ fontWeight: 850, color: "var(--app-fg)" }}>
                Copy-ready setup
              </Typography>
              <Typography component="dd" variant="body2" sx={{ mt: 1, color: "var(--app-muted)", lineHeight: 1.65 }}>
                Client, Docker, and CI snippets generated from runtime metadata.
              </Typography>
            </div>
          </dl>

          <div className="mt-10 grid max-w-2xl gap-3 sm:grid-cols-2">
            <div className="border border-[--app-border] bg-[--app-surface] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">Access model</p>
              <p className="mt-2 text-sm font-semibold text-[--app-fg]">
                {"Viewer -> Publisher -> Reviewer -> Admin"}
              </p>
            </div>
            <div className="border border-[--app-border] bg-[--app-surface] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">Security</p>
              <p className="mt-2 text-sm font-semibold text-[--app-fg]">Hashed passwords, tracked sessions, revocable tokens</p>
            </div>
          </div>
        </section>

        <section className="flex flex-col justify-center gap-4 bg-[--app-control-bg] p-6 sm:p-8 lg:p-10">
          {backendUnreachable ? (
            <Typography
              component="p"
              variant="body2"
              className="border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-800"
              role="status"
              sx={{ color: "#92400e" }}
            >
              Cannot reach the registry API at{" "}
              <Typography
                component="span"
                variant="caption"
                sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}
              >
                {process.env.REGISTRY_BACKEND_URL ?? "http://localhost:8000"}
              </Typography>
              . Start the Python registry (for example{" "}
              <Typography
                component="span"
                variant="caption"
                sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}
              >
                uv run python examples/securemcp/purecipher_registry.py
              </Typography>
              ) then refresh.
            </Typography>
          ) : null}
          <LoginFormGate bootstrapRequired={bootstrapRequired} />
        </section>
      </div>
    </div>
  );
}

function normalizeRegistryLanding(value: string | undefined): string | null {
  if (!value?.startsWith("/registry/")) return null;
  if (value.includes("://") || value.includes("\\")) return null;
  return value;
}


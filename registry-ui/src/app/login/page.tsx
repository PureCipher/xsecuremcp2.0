import Link from "next/link";
import { redirect } from "next/navigation";

import { getRegistrySession, getRegistryUserPreferences } from "@/lib/registryClient";
import { resolveRegistryLanding } from "@/lib/registryLanding";
import { LoginFormGate } from "./LoginFormGate";

export default async function LoginPage() {
  const sessionPayload = await getRegistrySession();

  if (sessionPayload?.auth_enabled === false) {
    redirect("/registry/app");
  }

  if (sessionPayload?.session != null) {
    const preferencesPayload = await getRegistryUserPreferences();
    redirect(
      resolveRegistryLanding(
        preferencesPayload?.preferences?.workspace?.defaultLandingPage,
        sessionPayload.session.role,
      ),
    );
  }

  const backendUnreachable = sessionPayload == null;
  const bootstrapRequired = sessionPayload?.bootstrap_required === true;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[--app-bg] px-4 py-10 text-sm text-[--app-fg]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(37,99,235,0.08),transparent_45%),radial-gradient(circle_at_top,rgba(14,165,233,0.10),transparent_42%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.3]"
        style={{
          backgroundImage:
            "linear-gradient(to right, var(--app-border) 1px, transparent 1px), linear-gradient(to bottom, var(--app-border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          maskImage:
            "radial-gradient(ellipse 75% 60% at 50% 25%, black 30%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 75% 60% at 50% 25%, black 30%, transparent 80%)",
        }}
      />
      <div className="pointer-events-none absolute -top-28 left-1/2 h-[24rem] w-[24rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(37,99,235,0.18),transparent_60%)] blur-3xl" />

      <main className="relative w-full max-w-[30rem]">
        <section className="overflow-hidden rounded-2xl border border-[--app-border] bg-[--app-surface]/95 shadow-[0_28px_90px_rgba(15,23,42,0.18)] ring-1 ring-[--app-surface-ring] backdrop-blur-xl">
          <div className="h-[3px] w-full bg-[linear-gradient(90deg,transparent,var(--app-accent),rgba(14,165,233,0.75),transparent)]" />

          <div className="space-y-6 p-6 sm:p-8">
            <header className="space-y-4">
              <div className="inline-flex items-center gap-3">
                <Logomark />
                <div className="flex flex-col leading-tight">
                  <span className="text-[10px] font-bold uppercase tracking-[0.28em] text-[--app-muted]">
                    PureCipher
                  </span>
                  <span className="text-[13px] font-semibold tracking-[-0.01em] text-[--app-fg]">
                    Secured MCP Registry
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[--app-muted]">
                  {bootstrapRequired ? "One-time setup" : "Sign in"}
                </p>
                <h1 className="text-3xl font-semibold tracking-[-0.04em] text-[--app-fg]">
                  {bootstrapRequired ? "Create your first admin" : "Sign in to the registry"}
                </h1>
                <p className="text-sm leading-6 text-[--app-muted]">
                  {bootstrapRequired
                    ? "Finish setup by creating the first admin account for this registry."
                    : "Use your registry credentials to continue. If you are only browsing, the public catalog is available without signing in."}
                </p>
              </div>
            </header>

            {backendUnreachable ? (
              <div
                role="status"
                className="flex gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-900"
              >
                <WarningIcon />
                <div className="space-y-1.5 text-[12px] leading-relaxed">
                  <p className="font-semibold">Registry API unreachable</p>
                  <p style={{ color: "#92400e" }}>
                    Cannot reach{" "}
                    <code className="rounded bg-amber-500/15 px-1 py-0.5 font-mono text-[11px]">
                      {process.env.REGISTRY_BACKEND_URL ?? "http://localhost:8000"}
                    </code>
                    . Start the Python registry (for example{" "}
                    <code className="rounded bg-amber-500/15 px-1 py-0.5 font-mono text-[11px]">
                      uv run python examples/securemcp/purecipher_registry.py
                    </code>
                    ) then refresh.
                  </p>
                </div>
              </div>
            ) : null}

            <LoginFormGate bootstrapRequired={bootstrapRequired} />

            <div className="space-y-2 text-center">
              <Link
                href="/public"
                className="text-[12px] font-medium text-[--app-muted] underline decoration-[--app-border] underline-offset-4 transition hover:text-[--app-fg]"
              >
                Browse the public registry
              </Link>
              {!bootstrapRequired ? (
                <div className="rounded-xl border border-[--app-border] bg-[--app-control-bg] px-4 py-3 text-left">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                    Need help signing in?
                  </p>
                  <p className="mt-2 text-[11px] leading-relaxed text-[--app-muted]">
                    Ask a registry admin for a one-time recovery token if you have lost
                    access to your account.
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Logomark() {
  return (
    <div className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-[--app-border] bg-[linear-gradient(135deg,var(--app-accent),rgb(14,165,233))] shadow-[0_8px_22px_rgba(37,99,235,0.35)]">
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-6 w-6 text-white"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="4" y="10" width="16" height="10" rx="2" />
        <path d="M8 10V7a4 4 0 1 1 8 0v3" />
        <circle cx="12" cy="15" r="1.2" fill="currentColor" />
      </svg>
    </div>
  );
}

function WarningIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="mt-0.5 h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
    </svg>
  );
}

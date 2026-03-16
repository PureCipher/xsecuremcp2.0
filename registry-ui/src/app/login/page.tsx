import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="grid w-full max-w-5xl gap-10 rounded-3xl bg-emerald-900/40 p-8 ring-1 ring-emerald-700/60 backdrop-blur-lg md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:p-10">
        <section className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-900/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-emerald-200">
            <span>PureCipher</span>
            <span className="h-1 w-1 rounded-full bg-emerald-400" />
            <span>Secured MCP Registry</span>
          </div>
          <div className="space-y-3">
            <h1 className="text-balance text-3xl font-semibold leading-tight text-emerald-50 md:text-4xl">
              Find a tool you can trust.
            </h1>
            <p className="max-w-xl text-sm leading-relaxed text-emerald-100/80">
              Browse a vetted catalog of MCP tools, understand what each one can access, and share your own
              listings with clear security context.
            </p>
          </div>
          <dl className="grid gap-4 text-xs text-emerald-100/90 sm:grid-cols-3">
            <div className="space-y-1 rounded-2xl bg-emerald-900/70 p-3 ring-1 ring-emerald-700/70">
              <dt className="font-medium text-emerald-50">Verified listings</dt>
              <dd>Attested manifests and certification levels for every published tool.</dd>
            </div>
            <div className="space-y-1 rounded-2xl bg-emerald-900/70 p-3 ring-1 ring-emerald-700/70">
              <dt className="font-medium text-emerald-50">Role-aware access</dt>
              <dd>Viewer, publisher, reviewer, and admin roles mapped to real workflows.</dd>
            </div>
            <div className="space-y-1 rounded-2xl bg-emerald-900/70 p-3 ring-1 ring-emerald-700/70">
              <dt className="font-medium text-emerald-50">Copy-ready setup</dt>
              <dd>Client, Docker, and CI snippets generated from runtime metadata.</dd>
            </div>
          </dl>
        </section>

        <section className="flex items-center justify-center">
          <LoginForm />
        </section>
      </div>
    </div>
  );
}


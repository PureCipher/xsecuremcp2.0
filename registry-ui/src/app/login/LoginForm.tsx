"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usernameFocused, setUsernameFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);

  function homeForRole(role: string | undefined): string {
    if (role === "publisher") return "/registry/publish/mine";
    if (role === "reviewer") return "/registry/review";
    if (role === "admin") return "/registry/app";
    return "/registry/app";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const username = String(formData.get("username") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    if (!username || !password) {
      setError("Enter a username and password.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { error?: string }
          | null;
        setError(payload?.error ?? "Sign in failed. Check your details.");
        setSubmitting(false);
        return;
      }

      const payload = (await response.json().catch(() => null)) as
        | { session?: { role?: string } }
        | null;
      router.push(homeForRole(payload?.session?.role));
    } catch (err) {
      console.error("Login error", err);
      setError("Unable to reach the registry. Try again.");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full overflow-hidden rounded-xl border border-[--app-border] bg-[--app-surface] shadow-[0_24px_70px_rgba(15,23,42,0.10)] ring-1 ring-[--app-surface-ring]"
    >
      {/* Top gradient hairline echoes the left-panel accent. */}
      <div className="h-[2px] w-full bg-[linear-gradient(90deg,transparent,var(--app-accent),rgb(14,165,233),transparent)]" />

      <div className="p-6 sm:p-7">
        <div className="mb-5 flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[--app-border] bg-[--app-control-bg] text-[--app-accent]">
            <ShieldGlyph />
          </div>
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[--app-muted]">
              Secure sign in
            </p>
            <h2 className="text-2xl font-semibold tracking-[-0.025em] text-[--app-fg]">
              Welcome back
            </h2>
            <p className="text-[13px] leading-6 text-[--app-muted]">
              Use your registry credentials to continue.
            </p>
          </div>
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="username"
            className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]"
          >
            Username
          </label>
          <div
            className={`relative flex items-center rounded-lg border bg-[--app-control-bg] transition ${
              usernameFocused
                ? "border-[--app-accent] ring-2 ring-[--app-accent]/25"
                : "border-[--app-border] hover:border-[--app-control-border]"
            }`}
          >
            <span className="pl-3 pr-2 text-[--app-muted]">
              <UserIcon />
            </span>
            <input
              id="username"
              name="username"
              placeholder="admin"
              autoComplete="username"
              onFocus={() => setUsernameFocused(true)}
              onBlur={() => setUsernameFocused(false)}
              className="w-full bg-transparent py-3 pr-3 text-sm text-[--app-fg] outline-none placeholder:text-[--app-muted]"
            />
          </div>
        </div>

        <div className="mt-4 space-y-1.5">
          <label
            htmlFor="password"
            className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]"
          >
            Password
          </label>
          <div
            className={`relative flex items-center rounded-lg border bg-[--app-control-bg] transition ${
              passwordFocused
                ? "border-[--app-accent] ring-2 ring-[--app-accent]/25"
                : "border-[--app-border] hover:border-[--app-control-border]"
            }`}
          >
            <span className="pl-3 pr-2 text-[--app-muted]">
              <PadlockIcon />
            </span>
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              name="password"
              placeholder="Enter password"
              autoComplete="current-password"
              onFocus={() => setPasswordFocused(true)}
              onBlur={() => setPasswordFocused(false)}
              className="w-full bg-transparent py-3 pr-2 text-sm text-[--app-fg] outline-none placeholder:text-[--app-muted]"
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((current) => !current)}
              className="flex h-full items-center justify-center px-3 text-[--app-muted] transition hover:text-[--app-fg] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[--app-accent]"
            >
              <PasswordEyeIcon visible={showPassword} />
            </button>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700"
          >
            <ErrorBangIcon />
            <span className="leading-relaxed">{error}</span>
          </div>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="group mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[linear-gradient(135deg,var(--app-accent),rgb(14,165,233))] px-4 py-3 text-sm font-semibold text-[--app-accent-contrast] shadow-[0_8px_22px_rgba(37,99,235,0.32)] transition hover:shadow-[0_10px_28px_rgba(37,99,235,0.42)] disabled:cursor-not-allowed disabled:opacity-70 disabled:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--app-accent] focus-visible:ring-offset-2 focus-visible:ring-offset-[--app-bg]"
        >
          {submitting ? (
            <>
              <Spinner /> Signing in…
            </>
          ) : (
            <>
              Sign in
              <ArrowRightIcon />
            </>
          )}
        </button>

        {/* Divider + future-SSO placeholders. They're disabled, but
            communicate "this is going to be enterprise-ready" without
            forcing a feature we haven't shipped. */}
        <div className="my-5 flex items-center gap-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          <span className="h-px flex-1 bg-[--app-border]" />
          or
          <span className="h-px flex-1 bg-[--app-border]" />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <DisabledSSO label="SAML" tooltip="SAML SSO — configurable in admin settings" />
          <DisabledSSO label="OIDC" tooltip="OIDC SSO — configurable in admin settings" />
        </div>
      </div>
    </form>
  );
}

// ── Icons ────────────────────────────────────────────────────

function ShieldGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}

function PadlockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="10" width="16" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 1 1 8 0v3" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 transition group-hover:translate-x-0.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function ErrorBangIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="mt-px h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </svg>
  );
}

function PasswordEyeIcon({ visible }: { visible: boolean }) {
  return visible ? (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
      <path d="M9.5 5.2A9.8 9.8 0 0 1 12 5c5 0 8.5 4.2 9.5 7a12 12 0 0 1-2.4 3.8" />
      <path d="M6.5 6.7A12 12 0 0 0 2.5 12C3.5 14.8 7 19 12 19a9.8 9.8 0 0 0 4.1-.9" />
    </svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function DisabledSSO({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <button
      type="button"
      disabled
      title={tooltip}
      aria-label={tooltip}
      className="inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-lg border border-dashed border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[--app-muted] opacity-60"
    >
      <KeyShape />
      {label}
    </button>
  );
}

function KeyShape() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7.5" cy="14.5" r="3.5" />
      <path d="m10 12 9-9" />
      <path d="m15 7 3 3" />
    </svg>
  );
}

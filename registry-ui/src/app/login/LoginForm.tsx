"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      className="w-full border border-[--app-border] bg-[--app-surface] p-6 shadow-[0_24px_70px_rgba(15,23,42,0.10)] ring-1 ring-[--app-surface-ring]"
    >
      <div className="mb-5 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Secure sign in
        </p>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-[--app-fg]">
          Welcome back
        </h2>
        <p className="text-sm leading-6 text-[--app-muted]">
          Use your registry credentials to continue to your role-based workspace.
        </p>
      </div>

      <div className="space-y-2">
        <label htmlFor="username" className="block text-xs font-semibold uppercase tracking-[0.08em] text-[--app-muted]">
          Username
        </label>
        <input
          id="username"
          name="username"
          placeholder="admin"
          autoComplete="username"
          className="w-full border border-[--app-border] bg-[--app-control-bg] px-4 py-3 text-sm text-[--app-fg] shadow-sm outline-none ring-0 transition placeholder:text-[--app-muted] focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]/25"
        />
      </div>
      <div className="mt-4 space-y-2">
        <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-[0.08em] text-[--app-muted]">
          Password
        </label>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            name="password"
            placeholder="Enter password"
            autoComplete="current-password"
            className="w-full border border-[--app-border] bg-[--app-control-bg] px-4 py-3 pr-14 text-sm text-[--app-fg] shadow-sm outline-none ring-0 transition placeholder:text-[--app-muted] focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]/25"
          />
          <button
            type="button"
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            onClick={() => setShowPassword((current) => !current)}
            className="absolute inset-y-0 right-0 flex w-12 items-center justify-center border-l border-[--app-border] text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[--app-accent]"
          >
            <PasswordEyeIcon visible={showPassword} />
          </button>
        </div>
      </div>
      {error ? (
        <p className="mt-4 border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700" role="alert">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        className="mt-5 inline-flex w-full items-center justify-center bg-[--app-accent] px-4 py-3 text-sm font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--app-accent] focus-visible:ring-offset-2 focus-visible:ring-offset-[--app-bg]"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

function PasswordEyeIcon({ visible }: { visible: boolean }) {
  return visible ? (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
      <path d="M9.5 5.2A9.8 9.8 0 0 1 12 5c5 0 8.5 4.2 9.5 7a12 12 0 0 1-2.4 3.8" />
      <path d="M6.5 6.7A12 12 0 0 0 2.5 12C3.5 14.8 7 19 12 19a9.8 9.8 0 0 0 4.1-.9" />
    </svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}


"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function BootstrapAdminForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const username = String(formData.get("username") ?? "admin").trim() || "admin";
    const displayName = String(formData.get("display_name") ?? "Registry Admin").trim();
    const password = String(formData.get("password") ?? "");

    if (password.length < 8) {
      setError("Use at least 8 characters for the admin password.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, display_name: displayName, password }),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { error?: string }
          | null;
        setError(payload?.error ?? "Admin setup failed. Refresh and try again.");
        setSubmitting(false);
        return;
      }

      router.push("/registry/app");
    } catch (err) {
      console.error("Admin setup error", err);
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
          One-time setup
        </p>
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-[--app-fg]">
          Create first admin
        </h2>
        <p className="text-sm leading-6 text-[--app-muted]">
          This creates the first admin account and signs you in.
        </p>
      </div>
      <div className="space-y-2">
        <label htmlFor="username" className="block text-xs font-semibold uppercase tracking-[0.08em] text-[--app-muted]">
          Admin username
        </label>
        <input
          id="username"
          name="username"
          defaultValue="admin"
          autoComplete="username"
          className="w-full border border-[--app-border] bg-[--app-control-bg] px-4 py-3 text-sm text-[--app-fg] shadow-sm outline-none ring-0 transition focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]/25"
        />
      </div>
      <div className="mt-4 space-y-2">
        <label htmlFor="display_name" className="block text-xs font-semibold uppercase tracking-[0.08em] text-[--app-muted]">
          Display name
        </label>
        <input
          id="display_name"
          name="display_name"
          defaultValue="Registry Admin"
          autoComplete="name"
          className="w-full border border-[--app-border] bg-[--app-control-bg] px-4 py-3 text-sm text-[--app-fg] shadow-sm outline-none ring-0 transition focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]/25"
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
            placeholder="At least 8 characters"
            autoComplete="new-password"
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
        {submitting ? "Creating admin..." : "Create admin"}
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

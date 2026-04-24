"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
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
      className="w-full max-w-xs space-y-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-5 ring-1 ring-[--app-surface-ring]"
    >
      <div className="space-y-1">
        <label htmlFor="username" className="block text-xs font-medium text-[--app-muted]">
          Username
        </label>
        <input
          id="username"
          name="username"
          placeholder="admin"
          autoComplete="username"
          className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-[--app-fg] shadow-sm outline-none ring-0 transition focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]"
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="password" className="block text-xs font-medium text-[--app-muted]">
          Password
        </label>
        <input
          id="password"
          type="password"
          name="password"
          placeholder="••••••••"
          autoComplete="current-password"
          className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-[--app-fg] shadow-sm outline-none ring-0 transition focus:border-[--app-accent] focus:ring-2 focus:ring-[--app-accent]"
        />
      </div>
      {error ? (
        <p className="text-xs text-rose-300" role="alert">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        className="inline-flex w-full items-center justify-center rounded-full bg-[--app-accent] px-4 py-2.5 text-xs font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--app-accent] focus-visible:ring-offset-2 focus-visible:ring-offset-[--app-bg]"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}


"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function LoginForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      router.push("/registry/app");
    } catch (err) {
      console.error("Login error", err);
      setError("Unable to reach the registry. Try again.");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-xs space-y-4 rounded-2xl bg-emerald-950/80 p-5 ring-1 ring-emerald-700/80"
    >
      <div className="space-y-1">
        <label htmlFor="username" className="block text-xs font-medium text-emerald-100">
          Username
        </label>
        <input
          id="username"
          name="username"
          placeholder="admin"
          autoComplete="username"
          className="w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 px-3 py-2 text-emerald-50 shadow-sm outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
        />
      </div>
      <div className="space-y-1">
        <label htmlFor="password" className="block text-xs font-medium text-emerald-100">
          Password
        </label>
        <input
          id="password"
          type="password"
          name="password"
          placeholder="••••••••"
          autoComplete="current-password"
          className="w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 px-3 py-2 text-emerald-50 shadow-sm outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
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
        className="inline-flex w-full items-center justify-center rounded-full bg-emerald-400 px-4 py-2.5 text-xs font-semibold text-emerald-950 shadow-sm transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-200 focus-visible:ring-offset-2 focus-visible:ring-offset-emerald-950"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}


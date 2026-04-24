"use client";

import { useEffect, useState } from "react";

import { LoginForm } from "./LoginForm";

/**
 * Mount the sign-in form only after hydration. Browsers/password managers often inject
 * values into username/password fields before React attaches; hydrating a server-rendered
 * <form> then mismatches the DOM → React #418.
 */
export function LoginFormGate() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        className="w-full max-w-xs space-y-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-5 ring-1 ring-[--app-surface-ring]"
        aria-busy="true"
        aria-label="Loading sign-in form"
      >
        <div className="space-y-1">
          <div className="h-3 w-16 animate-pulse rounded bg-[--app-chrome-bg]" />
          <div className="h-10 animate-pulse rounded-xl bg-[--app-chrome-bg]" />
        </div>
        <div className="space-y-1">
          <div className="h-3 w-14 animate-pulse rounded bg-[--app-chrome-bg]" />
          <div className="h-10 animate-pulse rounded-xl bg-[--app-chrome-bg]" />
        </div>
        <div className="h-10 animate-pulse rounded-full bg-[--app-accent]/35" />
      </div>
    );
  }

  return <LoginForm />;
}

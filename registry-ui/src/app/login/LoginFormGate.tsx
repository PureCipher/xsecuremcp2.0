"use client";

import { useEffect, useState } from "react";

import { LoginForm } from "./LoginForm";
import { BootstrapAdminForm } from "./BootstrapAdminForm";

/**
 * Mount the sign-in form only after hydration. Browsers/password managers often inject
 * values into username/password fields before React attaches; hydrating a server-rendered
 * <form> then mismatches the DOM → React #418.
 */
export function LoginFormGate({ bootstrapRequired = false }: { bootstrapRequired?: boolean }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        className="w-full space-y-4 border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]"
        aria-busy="true"
        aria-label="Loading sign-in form"
      >
        <div className="space-y-1">
          <div className="h-3 w-16 animate-pulse bg-[--app-chrome-bg]" />
          <div className="h-11 animate-pulse bg-[--app-chrome-bg]" />
        </div>
        <div className="space-y-1">
          <div className="h-3 w-14 animate-pulse bg-[--app-chrome-bg]" />
          <div className="h-11 animate-pulse bg-[--app-chrome-bg]" />
        </div>
        <div className="h-11 animate-pulse bg-[--app-accent]/35" />
      </div>
    );
  }

  return bootstrapRequired ? <BootstrapAdminForm /> : <LoginForm />;
}

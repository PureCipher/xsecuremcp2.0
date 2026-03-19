"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { NavIcon } from "@/components/security";

export function RegistryTopBar({
  canSubmit,
  canReview,
  canAdmin,
  cliActive,
  healthActive,
  settingsActive,
  onMenuToggle,
  menuOpen,
  onBrandClick,
}: {
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
  cliActive?: boolean;
  healthActive?: boolean;
  settingsActive?: boolean;
  onMenuToggle?: () => void;
  menuOpen?: boolean;
  onBrandClick?: () => void;
}) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const roleLabel = canAdmin ? "ADMIN" : canReview ? "REVIEWER" : canSubmit ? "PUBLISHER" : "USER";

  async function handleLogout() {
    setSigningOut(true);
    try {
      await fetch("/api/logout", { method: "POST" });
    } catch {
      // ignore – we still send the user back to login
    }
    router.push("/login");
  }

  return (
    <header className="fixed inset-x-0 top-0 z-50 h-14 border-b border-[--app-chrome-border] bg-[--app-chrome-bg] px-4 text-xs text-[--app-muted]">
      <div className="flex h-full w-full items-center gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={onMenuToggle}
            className="inline-flex items-center justify-center rounded-full border border-[--app-control-border] bg-[--app-control-bg] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted] transition hover:bg-[--app-hover-bg] sm:hidden"
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
          <button
            type="button"
            onClick={onBrandClick}
            className="flex items-center gap-3 rounded-2xl px-1 py-0.5 text-left transition hover:bg-[--app-hover-bg]"
            aria-label="Toggle sidebar"
          >
            <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[--app-accent] text-[11px] font-extrabold tracking-[0.16em] text-[--app-accent-contrast]">
              PC
            </div>
            <div className="min-w-0 leading-tight">
              <div className="truncate text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                PureCipher
              </div>
              <div className="truncate text-[11px] text-[--app-fg]">Secured MCP Registry</div>
            </div>
          </button>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <Link
            href="/registry/cli"
            className={`hidden items-center justify-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition sm:inline-flex ${
              cliActive
                ? "border-[--app-accent] bg-[--app-control-active-bg] text-[--app-fg]"
                : "border-[--app-control-border] bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg]"
            }`}
            aria-label="CLI"
            title="CLI"
          >
            <NavIcon name="cli" className="h-4 w-4" />
          </Link>
          <Link
            href="/registry/health"
            className={`inline-flex items-center justify-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition ${
              healthActive
                ? "border-[--app-accent] bg-[--app-control-active-bg] text-[--app-fg]"
                : "border-[--app-control-border] bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg]"
            }`}
            aria-label="Health"
            title="Health"
          >
            <NavIcon name="health" className="h-4 w-4" />
          </Link>
          <Link
            href="/registry/settings"
            className={`inline-flex items-center justify-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition ${
              settingsActive
                ? "border-[--app-accent] bg-[--app-control-active-bg] text-[--app-fg]"
                : "border-[--app-control-border] bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg]"
            }`}
            aria-label="Settings"
            title="Settings"
          >
            <NavIcon name="settings" className="h-4 w-4" />
          </Link>
          <span className="rounded-full bg-[--app-control-active-bg] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
            {roleLabel}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            disabled={signingOut}
            className="rounded-full border border-[--app-accent] px-3 py-1 text-[10px] font-semibold text-[--app-muted] transition hover:bg-[--app-control-active-bg] disabled:opacity-60"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}

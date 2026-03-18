"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";

export function RegistryTopBar({
  username,
  canSubmit,
  canReview,
  canAdmin,
}: {
  username: string;
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [signingOut, setSigningOut] = useState(false);

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
    <header className="border-b border-emerald-800/80 bg-emerald-950/95 px-4 py-3 text-xs text-emerald-100">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <div className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500 text-[10px] font-extrabold tracking-[0.16em] text-emerald-950">
            PC
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
              PureCipher
            </div>
            <div className="text-[11px] text-emerald-100/90">Secured MCP Registry</div>
          </div>
          <nav className="hidden items-center gap-2 text-[11px] text-emerald-200/90 sm:flex">
            <TopNavLink href="/registry/app" label="Tools" active={pathname.startsWith("/registry/app")} />
            {canSubmit ? (
              <TopNavLink
                href="/registry/publish"
                label="Publish"
                active={pathname.startsWith("/registry/publish")}
              />
            ) : null}
            <TopNavLink
              href="/registry/publishers"
              label="Publishers"
              active={pathname.startsWith("/registry/publishers")}
            />
            {canReview ? (
              <TopNavLink
                href="/registry/review"
                label="Review"
                active={pathname.startsWith("/registry/review")}
              />
            ) : null}
            {canReview ? (
              <TopNavLink
                href="/registry/policy"
                label="Policy"
                active={pathname.startsWith("/registry/policy")}
              />
            ) : null}
            {canReview ? (
              <TopNavLink
                href="/registry/provenance"
                label="Provenance"
                active={pathname.startsWith("/registry/provenance")}
              />
            ) : null}
            {canAdmin ? (
              <TopNavLink
                href="/registry/contracts"
                label="Contracts"
                active={pathname.startsWith("/registry/contracts")}
              />
            ) : null}
            {canAdmin ? (
              <TopNavLink
                href="/registry/consent"
                label="Consent"
                active={pathname.startsWith("/registry/consent")}
              />
            ) : null}
            {canAdmin ? (
              <TopNavLink
                href="/registry/reflexive"
                label="Reflexive"
                active={pathname.startsWith("/registry/reflexive")}
              />
            ) : null}
            <TopNavLink
              href="/registry/health"
              label="Health"
              active={pathname.startsWith("/registry/health")}
            />
            <TopNavLink
              href="/registry/settings"
              label="Settings"
              active={pathname.startsWith("/registry/settings")}
            />
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-emerald-900/70 px-2.5 py-1 text-[10px] font-medium text-emerald-100">
            Signed in as <span className="font-semibold">{username}</span>
          </span>
          {canAdmin ? (
            <span className="rounded-full bg-emerald-500/20 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
              Admin
            </span>
          ) : canReview ? (
            <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
              Reviewer
            </span>
          ) : canSubmit ? (
            <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
              Publisher
            </span>
          ) : null}
          <button
            type="button"
            onClick={handleLogout}
            disabled={signingOut}
            className="rounded-full border border-emerald-500/80 px-3 py-1 text-[10px] font-semibold text-emerald-100 transition hover:bg-emerald-500/10 disabled:opacity-60"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}

function TopNavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`rounded-full px-2.5 py-1 transition ${
        active
          ? "bg-emerald-800/80 text-emerald-50"
          : "hover:bg-emerald-900/70 hover:text-emerald-50"
      }`}
    >
      {label}
    </Link>
  );
}

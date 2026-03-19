"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { NavIcon } from "@/components/security";
import { RegistryTopBar } from "./topbar";
import { useAppTheme } from "@/hooks/useAppTheme";

type Props = {
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
  children: React.ReactNode;
};

type NavItem = {
  href: string;
  label: string;
  icon: Parameters<typeof NavIcon>[0]["name"];
  enabled: boolean;
  active: boolean;
};

export function RegistryShell({ canSubmit, canReview, canAdmin, children }: Props) {
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { themeId } = useAppTheme();
  const year = new Date().getFullYear();

  useEffect(() => {
    // Apply theme to document root so `body { background: var(--app-bg) }` updates.
    if (typeof document === "undefined") return;
    document.documentElement.dataset.appTheme = themeId;
  }, [themeId]);

  const toolkitItems: NavItem[] = useMemo(
    () => [
      {
        href: "/registry/app",
        label: "Tools",
        icon: "tools",
        enabled: true,
        active: pathname.startsWith("/registry/app"),
      },
      {
        href: "/registry/publish",
        label: "Publish",
        icon: "publish",
        enabled: canSubmit,
        active: pathname.startsWith("/registry/publish"),
      },
      {
        href: "/registry/publishers",
        label: "Publishers",
        icon: "publishers",
        enabled: true,
        active: pathname.startsWith("/registry/publishers"),
      },
      {
        href: "/registry/review",
        label: "Review",
        icon: "review",
        enabled: canReview,
        active: pathname.startsWith("/registry/review"),
      },
    ],
    [pathname, canSubmit, canReview],
  );

  const governanceItems: NavItem[] = useMemo(
    () => [
      {
        href: "/registry/policy",
        label: "Policy Kernel",
        icon: "policy",
        enabled: canReview,
        active: pathname.startsWith("/registry/policy"),
      },
      {
        href: "/registry/contracts",
        label: "Contract Broker",
        icon: "contracts",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/contracts"),
      },
      {
        href: "/registry/provenance",
        label: "Provenance Ledger",
        icon: "provenance",
        enabled: canReview,
        active: pathname.startsWith("/registry/provenance"),
      },
      {
        href: "/registry/reflexive",
        label: "Reflexive Core",
        icon: "reflexive",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/reflexive"),
      },
      {
        href: "/registry/consent",
        label: "Consent Graph",
        icon: "consent",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/consent"),
      },
    ],
    [pathname, canReview, canAdmin],
  );

  function closeMobileSidebar() {
    setMobileSidebarOpen(false);
  }

  const sidebarWidthClass = sidebarCollapsed ? "w-16" : "w-56";

  return (
    <div data-app-theme={themeId} className="h-screen bg-[--app-bg] text-sm text-[--app-fg]">
      <RegistryTopBar
        canSubmit={canSubmit}
        canReview={canReview}
        canAdmin={canAdmin}
        cliActive={pathname.startsWith("/registry/cli")}
        healthActive={pathname.startsWith("/registry/health")}
        settingsActive={pathname.startsWith("/registry/settings")}
        onMenuToggle={() => setMobileSidebarOpen((open) => !open)}
        menuOpen={mobileSidebarOpen}
        onBrandClick={() => {
          if (typeof window !== "undefined" && window.innerWidth < 640) {
            setMobileSidebarOpen((open) => !open);
          } else {
            setSidebarCollapsed((collapsed) => !collapsed);
          }
        }}
      />

      <footer className="fixed inset-x-0 bottom-0 z-40 h-12 border-t border-[--app-chrome-border] bg-[--app-chrome-bg] px-4 text-[11px] text-[--app-muted]">
        <div className="flex h-full w-full items-center justify-between">
          <span>© {year} PureCipher. All rights reserved.</span>
          <span className="hidden sm:inline">Secured MCP Registry</span>
        </div>
      </footer>

      <div className="fixed inset-x-0 bottom-12 top-14 flex w-full overflow-hidden">
        <aside
          className={`relative hidden shrink-0 border-r border-[--app-chrome-border] bg-[--app-chrome-bg] ${sidebarWidthClass} sm:block`}
        >
          <div className="flex h-full flex-col p-3">
            <nav className="mt-2 grid gap-4">
              <SidebarSection
                title="Secured MCP Tool Kit"
                items={toolkitItems}
                collapsed={sidebarCollapsed}
              />
              <SidebarSection
                title="Governance"
                items={governanceItems}
                collapsed={sidebarCollapsed}
              />
            </nav>
          </div>
        </aside>

        {mobileSidebarOpen ? (
          <div
            className="fixed inset-x-0 bottom-12 top-14 z-40 sm:hidden"
            role="dialog"
            aria-modal="true"
          >
            <button
              type="button"
              aria-label="Close menu"
              className="absolute inset-0 bg-[--app-scrim]"
              onClick={closeMobileSidebar}
            />
            <aside className="absolute left-0 top-0 h-full w-72 border-r border-[--app-chrome-border] bg-[--app-chrome-bg] p-3">
              <div className="flex items-center justify-end">
                <button
                  type="button"
                  aria-label="Close menu"
                  onClick={closeMobileSidebar}
                  className="inline-flex items-center justify-center rounded-full border border-[--app-control-border] bg-[--app-control-bg] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted] transition hover:bg-[--app-hover-bg]"
                >
                  Close
                </button>
              </div>

              <nav className="mt-3 grid gap-4">
                <SidebarSection
                  title="Secured MCP Tool Kit"
                  items={toolkitItems}
                  onNavigate={closeMobileSidebar}
                />
                <SidebarSection
                  title="Governance"
                  items={governanceItems}
                  onNavigate={closeMobileSidebar}
                />
              </nav>
            </aside>
          </div>
        ) : null}

        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function SidebarLink({
  href,
  label,
  icon,
  active,
  collapsed,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: Parameters<typeof NavIcon>[0]["name"];
  active: boolean;
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-[11px] font-medium transition ${
        active
          ? "bg-[--app-active-bg] text-[--app-fg] ring-1 ring-[--app-active-ring]"
          : "text-[--app-muted] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
      }`}
      aria-label={label}
    >
      <span className={`${collapsed ? "mx-auto" : ""} shrink-0 text-[--app-muted]`}>
        <NavIcon name={icon} />
      </span>
      {!collapsed ? <span className="min-w-0 truncate">{label}</span> : null}
    </Link>
  );
}

function SidebarSection({
  title,
  items,
  collapsed,
  onNavigate,
}: {
  title: string;
  items: NavItem[];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const visible = items.filter((item) => item.enabled);
  if (visible.length === 0) return null;

  return (
    <div className="grid gap-1">
      {!collapsed ? (
        <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          {title}
        </p>
      ) : (
        <div className="my-2 h-px w-full bg-[--app-chrome-border]" aria-hidden />
      )}
      <div className="grid gap-1">
        {visible.map((item) => (
          <SidebarLink
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            active={item.active}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  );
}


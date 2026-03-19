"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { useCliTerminalPreferences } from "@/hooks/useCliTerminalPreferences";
import { CLI_TERMINAL_THEMES, getCliTerminalTheme } from "@/lib/cliTerminalThemes";

import { CliCheatsheet } from "./CliCheatsheet";
import { SecureCliTerminal } from "./SecureCliTerminal";

type Tab = { id: string; label: string };

type SessionState = { tabs: Tab[]; activeId: string };

function newSessionLabel(index: number) {
  return `Session ${index}`;
}

function initialSession(): SessionState {
  const id = "session-1";
  return { tabs: [{ id, label: newSessionLabel(1) }], activeId: id };
}

type Props = {
  defaultMcpUrl: string;
  allowedOrigin: string;
};

export function CliDeveloperWorkspace({ defaultMcpUrl, allowedOrigin }: Props) {
  const { prefs, setThemeId, setFontSize } = useCliTerminalPreferences();
  const theme = useMemo(() => getCliTerminalTheme(prefs.themeId), [prefs.themeId]);

  const [session, setSession] = useState<SessionState>(initialSession);

  const addTab = useCallback(() => {
    setSession((s) => {
      const id = crypto.randomUUID();
      return {
        tabs: [...s.tabs, { id, label: newSessionLabel(s.tabs.length + 1) }],
        activeId: id,
      };
    });
  }, []);

  const closeTab = useCallback((id: string) => {
    setSession((s) => {
      if (s.tabs.length <= 1) return s;
      const idx = s.tabs.findIndex((t) => t.id === id);
      const tabs = s.tabs.filter((t) => t.id !== id);
      let activeId = s.activeId;
      if (id === s.activeId) {
        const fb = tabs[Math.max(0, idx - 1)] ?? tabs[0];
        activeId = fb!.id;
      }
      return { tabs, activeId };
    });
  }, []);

  const { tabs, activeId } = session;

  return (
    <div className="flex flex-col gap-4">
      <header className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">Developer access</p>
        <h1 className="text-2xl font-semibold text-[--app-fg]">SecureMCP CLI</h1>
        <p className="max-w-3xl text-[12px] leading-relaxed text-[--app-muted]">
          Multi-session terminal with macOS-style color profiles. Each tab is an independent MCP shell. The cheatsheet stays
          docked on the right for quick copy-paste.
        </p>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_min(360px,36%)] lg:items-start">
        <div className="flex min-h-[min(640px,calc(100vh-11rem))] min-w-0 flex-col overflow-hidden border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring]">
          <div className="flex flex-wrap items-center gap-2 border-b border-[--app-border] px-3 py-2.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">Profile</span>
            <label className="sr-only" htmlFor="cli-theme">
              Terminal theme
            </label>
            <select
              id="cli-theme"
              value={prefs.themeId}
              onChange={(e) => setThemeId(e.target.value)}
              className="max-w-[220px] rounded-lg border border-[--app-border] bg-[--app-control-bg] px-2 py-1 text-[11px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
            >
              {CLI_TERMINAL_THEMES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
            <span className="text-[10px] text-[--app-muted]">({theme.macStyle})</span>

            <span className="mx-1 hidden h-4 w-px bg-[--app-border] sm:inline" aria-hidden />

            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">Font</span>
            <label className="sr-only" htmlFor="cli-font">
              Font size
            </label>
            <select
              id="cli-font"
              value={prefs.fontSize}
              onChange={(e) => setFontSize(Number(e.target.value))}
              className="rounded-lg border border-[--app-border] bg-[--app-control-bg] px-2 py-1 text-[11px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
            >
              {[10, 11, 12, 13, 14, 15, 16, 18].map((n) => (
                <option key={n} value={n}>
                  {n}px
                </option>
              ))}
            </select>

            <Link
              href="/registry/settings#browser-cli-terminal"
              className="ml-auto text-[10px] font-medium uppercase tracking-[0.12em] text-[--app-muted] underline decoration-[--app-accent] underline-offset-2 hover:text-[--app-fg]"
            >
              Settings
            </Link>
          </div>

          <div className="flex shrink-0 items-stretch gap-0.5 overflow-x-auto border-b border-[--app-border] bg-[--app-control-bg] px-1 pt-1">
            {tabs.map((t) => {
              const active = t.id === activeId;
              return (
                <div
                  key={t.id}
                  className={`flex min-w-0 items-center ring-1 ${
                    active ? "bg-[--app-surface] ring-[--app-accent]" : "bg-[--app-control-bg] ring-[--app-surface-ring]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSession((s) => ({ ...s, activeId: t.id }))}
                    className={`max-w-[140px] truncate px-3 py-2 text-left text-[11px] font-medium ${
                      active ? "text-[--app-fg]" : "text-[--app-muted] hover:text-[--app-fg]"
                    }`}
                  >
                    {t.label}
                  </button>
                  {tabs.length > 1 ? (
                    <button
                      type="button"
                      aria-label={`Close ${t.label}`}
                      onClick={() => closeTab(t.id)}
                      className="px-2 py-2 text-[12px] text-[--app-muted] hover:text-rose-300"
                    >
                      ×
                    </button>
                  ) : null}
                </div>
              );
            })}
            <button
              type="button"
              onClick={addTab}
              className="mb-0.5 self-end border border-dashed border-[--app-border] px-3 py-1.5 text-[11px] font-semibold text-[--app-muted] hover:border-[--app-accent] hover:text-[--app-fg]"
              title="New terminal tab"
            >
              +
            </button>
          </div>

          <div className="relative min-h-0 flex-1 p-2">
            {tabs.map((t) => (
              <div
                key={t.id}
                className={`absolute inset-2 ${
                  t.id === activeId ? "z-10 opacity-100" : "z-0 opacity-0 pointer-events-none"
                }`}
                aria-hidden={t.id !== activeId}
              >
                <SecureCliTerminal
                  key={`${t.id}-${prefs.themeId}-${prefs.fontSize}`}
                  defaultMcpUrl={defaultMcpUrl}
                  theme={theme}
                  fontSize={prefs.fontSize}
                  fontFamily={prefs.fontFamily}
                  fontWeight={prefs.fontWeight}
                  fontWeightBold={prefs.fontWeightBold}
                  visible={t.id === activeId}
                />
              </div>
            ))}
          </div>
        </div>

        <CliCheatsheet defaultMcpUrl={defaultMcpUrl} allowedOrigin={allowedOrigin} className="lg:sticky lg:top-20" />
      </div>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
        <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">Full Python CLI</h2>
        <p className="mt-2 text-[11px] leading-relaxed text-[--app-muted]">
          For <span className="font-mono">stdio</span>, <span className="font-mono">securemcp run</span>, install recipes, and
          OAuth, use the local <span className="font-mono">securemcp</span> binary (<span className="font-mono">uv sync</span> in
          this repo).
        </p>
      </section>
    </div>
  );
}

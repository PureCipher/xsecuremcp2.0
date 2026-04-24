"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { Box, Typography } from "@mui/material";

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
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Developer access
        </Typography>
        <Typography variant="h5" sx={{ color: "var(--app-fg)" }}>
          SecureMCP CLI
        </Typography>
        <Typography variant="body2" sx={{ maxWidth: 960, color: "var(--app-muted)" }}>
          Multi-session terminal with macOS-style color profiles. Each tab is an independent MCP shell. The cheatsheet stays
          docked on the right for quick copy-paste.
        </Typography>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1fr_min(360px,36%)] lg:items-start">
        <div className="flex min-h-[min(640px,calc(100vh-11rem))] min-w-0 flex-col overflow-hidden border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring]">
          <div className="flex flex-wrap items-center gap-2 border-b border-[--app-border] px-3 py-2.5">
            <Typography component="span" variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.14em" }}>
              Profile
            </Typography>
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
            <Typography component="span" variant="caption" sx={{ color: "var(--app-muted)" }}>
              ({theme.macStyle})
            </Typography>

            <span className="mx-1 hidden h-4 w-px bg-[--app-border] sm:inline" aria-hidden />

            <Typography component="span" variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.14em" }}>
              Font
            </Typography>
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
              className="ml-auto underline decoration-[--app-accent] underline-offset-2 hover:text-[--app-fg]"
            >
              <Typography component="span" variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.12em" }}>
                Settings
              </Typography>
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
                    className={`max-w-[140px] truncate px-3 py-2 text-left ${
                      active ? "text-[--app-fg]" : "text-[--app-muted] hover:text-[--app-fg]"
                    }`}
                  >
                    <Typography component="span" variant="caption" sx={{ fontWeight: 600 }}>
                      {t.label}
                    </Typography>
                  </button>
                  {tabs.length > 1 ? (
                    <button
                      type="button"
                      aria-label={`Close ${t.label}`}
                      onClick={() => closeTab(t.id)}
                      className="px-2 py-2 text-[--app-muted] hover:text-rose-300"
                    >
                      <Typography component="span" variant="body2" sx={{ lineHeight: 1 }}>
                        ×
                      </Typography>
                    </button>
                  ) : null}
                </div>
              );
            })}
            <button
              type="button"
              onClick={addTab}
              className="mb-0.5 self-end border border-dashed border-[--app-border] px-3 py-1.5 text-[--app-muted] hover:border-[--app-accent] hover:text-[--app-fg]"
              title="New terminal tab"
            >
              <Typography component="span" variant="caption" sx={{ fontWeight: 700 }}>
                +
              </Typography>
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

      <Box
        component="section"
        sx={{
          borderRadius: 4,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-surface)",
          p: 2,
          boxShadow: "none",
        }}
      >
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Full Python CLI
        </Typography>
        <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)", lineHeight: 1.6 }}>
          For{" "}
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            stdio
          </Box>
          ,{" "}
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            securemcp run
          </Box>
          , install recipes, and OAuth, use the local{" "}
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            securemcp
          </Box>{" "}
          binary (
          <Box component="span" sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            uv sync
          </Box>{" "}
          in this repo).
        </Typography>
      </Box>
    </div>
  );
}

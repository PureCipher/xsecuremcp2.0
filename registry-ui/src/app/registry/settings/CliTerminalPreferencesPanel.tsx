"use client";

import Link from "next/link";

import { useCliTerminalPreferences } from "@/hooks/useCliTerminalPreferences";
import { CLI_TERMINAL_THEMES } from "@/lib/cliTerminalThemes";

export function CliTerminalPreferencesPanel() {
  const { prefs, setThemeId, setFontSize, setFontFamily, setFontWeight, setFontWeightBold } =
    useCliTerminalPreferences();

  return (
    <section
      id="browser-cli-terminal"
      className="scroll-mt-24 rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]"
    >
      <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">Browser CLI terminal</h2>
      <p className="mt-2 max-w-xl text-[11px] leading-relaxed text-[--app-muted]">
        Preferences for the in-browser SecureMCP CLI on{" "}
        <Link
          href="/registry/cli"
          className="font-mono text-[--app-muted] underline decoration-[--app-accent]"
        >
          /registry/cli
        </Link>
        . Stored in this browser only (<span className="font-mono">localStorage</span>).
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="settings-cli-theme"
            className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
          >
            Color profile
          </label>
          <p className="mt-0.5 text-[10px] text-[--app-muted]">Background & text — Terminal.app-style presets</p>
          <select
            id="settings-cli-theme"
            value={prefs.themeId}
            onChange={(e) => setThemeId(e.target.value)}
            className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
          >
            {CLI_TERMINAL_THEMES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label} — {t.description}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="settings-cli-font"
            className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
          >
            Monospace font size
          </label>
          <p className="mt-0.5 text-[10px] text-[--app-muted]">xterm font size (px)</p>
          <select
            id="settings-cli-font"
            value={prefs.fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
            className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
          >
            {[10, 11, 12, 13, 14, 15, 16, 18].map((n) => (
              <option key={n} value={n}>
                {n}px
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div>
          <label
            htmlFor="settings-cli-font-family"
            className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
          >
            Font
          </label>
          <p className="mt-0.5 text-[10px] text-[--app-muted]">Font family (regular + bold)</p>
          <select
            id="settings-cli-font-family"
            value={prefs.fontFamily}
            onChange={(e) => setFontFamily(e.target.value)}
            className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
          >
            {[
              "JetBrains Mono",
              "Fira Code",
              "IBM Plex Mono",
              "Source Code Pro",
              "ui-monospace",
            ].map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="settings-cli-font-weight"
            className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
          >
            Weight (regular)
          </label>
          <p className="mt-0.5 text-[10px] text-[--app-muted]">Normal text weight</p>
          <select
            id="settings-cli-font-weight"
            value={prefs.fontWeight}
            onChange={(e) => setFontWeight(e.target.value as "normal" | "bold")}
            className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
          >
            <option value="normal">Regular</option>
            <option value="bold">Bold</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="settings-cli-font-weight-bold"
            className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
          >
            Weight (bold)
          </label>
          <p className="mt-0.5 text-[10px] text-[--app-muted]">Bold text weight</p>
          <select
            id="settings-cli-font-weight-bold"
            value={prefs.fontWeightBold}
            onChange={(e) => setFontWeightBold(e.target.value as "normal" | "bold")}
            className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
          >
            <option value="bold">Bold</option>
            <option value="normal">Regular</option>
          </select>
        </div>
      </div>
    </section>
  );
}

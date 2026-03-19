"use client";

import { APP_THEMES, type AppThemeId } from "@/lib/appThemes";
import { useAppTheme } from "@/hooks/useAppTheme";

export function AppThemePreferencesPanel() {
  const { themeId, setThemeId } = useAppTheme();

  return (
    <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
      <header className="space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
          Appearance
        </p>
        <p className="max-w-xl text-[11px] text-[--app-muted]">
          Sets the registry chrome theme (top bar, sidebar, and footer). Terminal color profiles are
          configured separately below.
        </p>
      </header>

      <div className="mt-4">
        <label
          htmlFor="settings-app-theme"
          className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]"
        >
          Application theme
        </label>
        <p className="mt-0.5 text-[10px] text-[--app-muted]">Controls registry UI surfaces and accents</p>
        <select
          id="settings-app-theme"
          value={themeId}
          onChange={(e) => setThemeId(e.target.value as AppThemeId)}
          className="mt-2 w-full rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 text-[12px] text-[--app-fg] focus:outline-none focus:ring-1 focus:ring-[--app-accent]"
        >
          {APP_THEMES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label} — {t.description}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}


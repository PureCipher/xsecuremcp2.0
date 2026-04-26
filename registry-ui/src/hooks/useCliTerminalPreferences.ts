"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";

import { DEFAULT_CLI_THEME_ID } from "@/lib/cliTerminalThemes";

export const CLI_TERMINAL_PREFS_STORAGE_KEY = "purecipher.registry.cliTerminal.v3";

export type CliTerminalPreferences = {
  themeId: string;
  /** xterm font size in px */
  fontSize: number;
  fontFamily: string;
  /** xterm fontWeight */
  fontWeight: "normal" | "bold";
  /** xterm fontWeightBold */
  fontWeightBold: "normal" | "bold";
};

const DEFAULT_PREFERENCES: CliTerminalPreferences = {
  themeId: DEFAULT_CLI_THEME_ID,
  fontSize: 12,
  fontFamily: "SF Mono",
  fontWeight: "normal",
  fontWeightBold: "bold",
};

function readPrefsFromStorage(): CliTerminalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = localStorage.getItem(CLI_TERMINAL_PREFS_STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<CliTerminalPreferences>;
    return {
      themeId: typeof parsed.themeId === "string" ? parsed.themeId : DEFAULT_PREFERENCES.themeId,
      fontSize:
        typeof parsed.fontSize === "number" && parsed.fontSize >= 10 && parsed.fontSize <= 22
          ? parsed.fontSize
          : DEFAULT_PREFERENCES.fontSize,
      fontFamily:
        typeof parsed.fontFamily === "string" && parsed.fontFamily.trim()
          ? parsed.fontFamily
          : DEFAULT_PREFERENCES.fontFamily,
      fontWeight:
        parsed.fontWeight === "normal" || parsed.fontWeight === "bold"
          ? parsed.fontWeight
          : DEFAULT_PREFERENCES.fontWeight,
      fontWeightBold:
        parsed.fontWeightBold === "normal" || parsed.fontWeightBold === "bold"
          ? parsed.fontWeightBold
          : DEFAULT_PREFERENCES.fontWeightBold,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function writePrefsToStorage(prefs: CliTerminalPreferences) {
  try {
    localStorage.setItem(CLI_TERMINAL_PREFS_STORAGE_KEY, JSON.stringify(prefs));
    window.dispatchEvent(new Event("purecipher-cli-terminal-prefs"));
  } catch {
    /* ignore quota / private mode */
  }
}

/**
 * Browser CLI terminal preferences (theme, font). Owned by /registry/cli.
 */
export function useCliTerminalPreferences(): {
  prefs: CliTerminalPreferences;
  setPrefs: (next: Partial<CliTerminalPreferences>) => void;
  setThemeId: (themeId: string) => void;
  setFontSize: (fontSize: number) => void;
  setFontFamily: (fontFamily: string) => void;
  setFontWeight: (fontWeight: "normal" | "bold") => void;
  setFontWeightBold: (fontWeightBold: "normal" | "bold") => void;
} {
  // Match SSR first paint; sync from localStorage after mount (avoids React hydration #418).
  const [prefs, setPrefsState] = useState<CliTerminalPreferences>(DEFAULT_PREFERENCES);

  useLayoutEffect(() => {
    setPrefsState(readPrefsFromStorage());
  }, []);

  useEffect(() => {
    const sync = () => setPrefsState(readPrefsFromStorage());
    window.addEventListener("storage", sync);
    window.addEventListener("purecipher-cli-terminal-prefs", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("purecipher-cli-terminal-prefs", sync);
    };
  }, []);

  const setPrefs = useCallback((next: Partial<CliTerminalPreferences>) => {
    setPrefsState((prev) => {
      const merged: CliTerminalPreferences = { ...prev, ...next };
      if (merged.fontSize < 10) merged.fontSize = 10;
      if (merged.fontSize > 22) merged.fontSize = 22;
      writePrefsToStorage(merged);
      return merged;
    });
  }, []);

  const setThemeId = useCallback(
    (themeId: string) => {
      setPrefs({ themeId });
    },
    [setPrefs],
  );

  const setFontSize = useCallback(
    (fontSize: number) => {
      setPrefs({ fontSize });
    },
    [setPrefs],
  );

  const setFontFamily = useCallback(
    (fontFamily: string) => {
      setPrefs({ fontFamily });
    },
    [setPrefs],
  );

  const setFontWeight = useCallback(
    (fontWeight: "normal" | "bold") => {
      setPrefs({ fontWeight });
    },
    [setPrefs],
  );

  const setFontWeightBold = useCallback(
    (fontWeightBold: "normal" | "bold") => {
      setPrefs({ fontWeightBold });
    },
    [setPrefs],
  );

  return {
    prefs,
    setPrefs,
    setThemeId,
    setFontSize,
    setFontFamily,
    setFontWeight,
    setFontWeightBold,
  };
}

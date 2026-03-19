"use client";

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_APP_THEME_ID, type AppThemeId } from "@/lib/appThemes";

export const APP_THEME_STORAGE_KEY = "purecipher.registry.appTheme.v1";

type StoredTheme = {
  themeId: AppThemeId;
};

const DEFAULT_STORED_THEME: StoredTheme = {
  themeId: DEFAULT_APP_THEME_ID,
};

function readThemeFromStorage(): StoredTheme {
  if (typeof window === "undefined") return DEFAULT_STORED_THEME;
  try {
    const raw = localStorage.getItem(APP_THEME_STORAGE_KEY);
    if (!raw) return DEFAULT_STORED_THEME;
    const parsed = JSON.parse(raw) as Partial<StoredTheme>;
    const validThemeId: AppThemeId | null =
      parsed.themeId === "emerald-forest" || parsed.themeId === "slate-night" ? parsed.themeId : null;
    return {
      themeId: validThemeId ?? DEFAULT_STORED_THEME.themeId,
    };
  } catch {
    return DEFAULT_STORED_THEME;
  }
}

function writeThemeToStorage(next: StoredTheme) {
  try {
    localStorage.setItem(APP_THEME_STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event("purecipher-app-theme"));
  } catch {
    /* ignore quota / private mode */
  }
}

export function useAppTheme(): {
  themeId: AppThemeId;
  setThemeId: (themeId: AppThemeId) => void;
} {
  const [stored, setStored] = useState<StoredTheme>(() =>
    typeof window !== "undefined" ? readThemeFromStorage() : DEFAULT_STORED_THEME,
  );

  useEffect(() => {
    const sync = () => setStored(readThemeFromStorage());
    window.addEventListener("storage", sync);
    window.addEventListener("purecipher-app-theme", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("purecipher-app-theme", sync);
    };
  }, []);

  const setThemeId = useCallback((themeId: AppThemeId) => {
    setStored(() => {
      const next: StoredTheme = { themeId };
      writeThemeToStorage(next);
      return next;
    });
  }, []);

  return { themeId: stored.themeId, setThemeId };
}


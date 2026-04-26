"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";

import {
  DEFAULT_APP_THEME_ID,
  isAppThemeId,
  type AppThemeId,
} from "@/lib/appThemes";

export const APP_THEME_STORAGE_KEY = "purecipher.registry.appTheme.v1";

type StoredTheme = {
  themeId: AppThemeId;
};

const DEFAULT_STORED_THEME: StoredTheme = {
  themeId: DEFAULT_APP_THEME_ID,
};

function applyThemeToDocument(themeId: AppThemeId) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.appTheme = themeId;
}

function readThemeFromStorage(): StoredTheme {
  if (typeof window === "undefined") return DEFAULT_STORED_THEME;
  try {
    const raw = localStorage.getItem(APP_THEME_STORAGE_KEY);
    if (!raw) return DEFAULT_STORED_THEME;
    const parsed = JSON.parse(raw) as Partial<StoredTheme>;
    const candidate = parsed.themeId;
    return {
      themeId:
        typeof candidate === "string" && isAppThemeId(candidate)
          ? candidate
          : DEFAULT_STORED_THEME.themeId,
    };
  } catch {
    return DEFAULT_STORED_THEME;
  }
}

function writeThemeToStorage(next: StoredTheme) {
  try {
    applyThemeToDocument(next.themeId);
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
  // Must match SSR first paint: never read localStorage in the useState initializer
  // (client would hydrate with a different MUI tree than the server → React #418).
  const [stored, setStored] = useState<StoredTheme>(DEFAULT_STORED_THEME);

  useLayoutEffect(() => {
    const next = readThemeFromStorage();
    applyThemeToDocument(next.themeId);
    setStored(next);
  }, []);

  useEffect(() => {
    const sync = () => {
      const next = readThemeFromStorage();
      applyThemeToDocument(next.themeId);
      setStored(next);
    };
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

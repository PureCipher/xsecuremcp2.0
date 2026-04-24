"use client";

import { useEffect, useLayoutEffect } from "react";

import { useAppTheme } from "@/hooks/useAppTheme";
import { NAVY_COMMAND_THEME_ID, PAPER_CONTRAST_THEME_ID } from "@/lib/appThemes";

export function AppThemeRoot({ children }: { children: React.ReactNode }) {
  const { themeId, setThemeId } = useAppTheme();

  useLayoutEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.appTheme = themeId;
  }, [themeId]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!e.ctrlKey || !e.shiftKey) return;
      if (e.key !== "c" && e.key !== "C") return;
      e.preventDefault();
      setThemeId(themeId === PAPER_CONTRAST_THEME_ID ? NAVY_COMMAND_THEME_ID : PAPER_CONTRAST_THEME_ID);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setThemeId, themeId]);

  return children;
}

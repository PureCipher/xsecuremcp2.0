"use client";

import { CssBaseline } from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { useMemo } from "react";

import { useAppTheme } from "@/hooks/useAppTheme";

export function MuiThemeRoot({ children }: { children: React.ReactNode }) {
  const { themeId } = useAppTheme();

  const theme = useMemo(() => {
    const isLight = themeId === "paper-contrast" || themeId === "sandstone-day";
    return createTheme({
      palette: {
        mode: isLight ? "light" : "dark",
        background: {
          // Must be concrete colors: MUI parses/manipulates these.
          // We still visually align via CSS variables in globals/CssBaseline.
          default: isLight ? "#f8fafc" : "#0b1220",
          paper: isLight ? "#ffffff" : "#0f172a",
        },
        text: {
          // Must be concrete colors: MUI parses/manipulates these.
          primary: isLight ? "#0f172a" : "#e2e8f0",
          secondary: isLight ? "#475569" : "#94a3b8",
        },
        primary: {
          // MUI expects a concrete color value here (it parses the string).
          // We still visually align via CSS variable-driven surfaces/text,
          // but keep palette colors as real hex to avoid SSR/prerender crashes.
          main: isLight ? "#0ea5a6" : "#22d3ee",
          contrastText: "#0b1220",
        },
        divider: isLight ? "rgba(15, 23, 42, 0.14)" : "rgba(226, 232, 240, 0.14)",
      },
      shape: {
        borderRadius: 14,
      },
      typography: {
        fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial",
        button: {
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          fontWeight: 700,
          fontSize: "0.7rem",
        },
      },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              backgroundColor: "var(--app-bg)",
              color: "var(--app-fg)",
            },
          },
        },
        MuiButton: {
          defaultProps: {
            disableElevation: true,
          },
          styleOverrides: {
            root: {
              borderRadius: 9999,
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
            },
          },
        },
      },
    });
  }, [themeId]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}


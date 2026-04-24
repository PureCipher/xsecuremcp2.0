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
        // Keep MUI defaults (14px base) but make variants explicit so
        // mixed Tailwind + MUI screens converge as we migrate.
        fontSize: 14,
        h4: {
          fontWeight: 800,
          fontSize: "1.9rem",
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
        },
        h5: {
          fontWeight: 800,
          fontSize: "1.45rem",
          lineHeight: 1.2,
          letterSpacing: "-0.015em",
        },
        h6: {
          fontWeight: 800,
          fontSize: "1.15rem",
          lineHeight: 1.25,
          letterSpacing: "-0.01em",
        },
        body1: {
          fontSize: "0.95rem",
          lineHeight: 1.55,
        },
        body2: {
          fontSize: "0.875rem",
          lineHeight: 1.55,
        },
        caption: {
          fontSize: "0.75rem",
          lineHeight: 1.5,
        },
        overline: {
          fontSize: "0.7rem",
          lineHeight: 1.4,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          fontWeight: 800,
        },
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
        MuiTypography: {
          defaultProps: {
            variantMapping: {
              // Prefer semantic tags while keeping visual variants.
              h4: "h1",
              h5: "h2",
              h6: "h3",
              subtitle1: "p",
              subtitle2: "p",
              body1: "p",
              body2: "p",
              caption: "span",
              overline: "span",
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


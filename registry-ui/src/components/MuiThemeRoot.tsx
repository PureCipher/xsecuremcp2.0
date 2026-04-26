"use client";

import { CssBaseline } from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { useMemo } from "react";

import { useAppTheme } from "@/hooks/useAppTheme";

export function MuiThemeRoot({ children }: { children: React.ReactNode }) {
  const { themeId } = useAppTheme();

  const theme = useMemo(() => {
    const isDark = themeId === "slate-night";
    const isLight = !isDark;
    return createTheme({
      palette: {
        mode: isLight ? "light" : "dark",
        background: {
          // Must be concrete colors: MUI parses/manipulates these.
          // We still visually align via CSS variables in globals/CssBaseline.
          default: isLight ? "#f6f8fb" : "#0f172a",
          paper: isLight ? "#ffffff" : "#1e293b",
        },
        text: {
          // Must be concrete colors: MUI parses/manipulates these.
          primary: isLight ? "#111827" : "#f8fafc",
          secondary: isLight ? "#64748b" : "#cbd5e1",
        },
        primary: {
          // MUI expects a concrete color value here (it parses the string).
          // We still visually align via CSS variable-driven surfaces/text,
          // but keep palette colors as real hex to avoid SSR/prerender crashes.
          main: isLight ? "#2563eb" : "#38bdf8",
          contrastText: isLight ? "#ffffff" : "#020617",
        },
        divider: isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(226, 232, 240, 0.12)",
      },
      shape: {
        borderRadius: 0,
      },
      typography: {
        fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial",
        // Keep MUI defaults (14px base) but make variants explicit so
        // mixed Tailwind + MUI screens converge as we migrate.
        fontSize: 14,
        h4: {
          fontWeight: 750,
          fontSize: "1.875rem",
          lineHeight: 1.18,
          letterSpacing: "-0.02em",
        },
        h5: {
          fontWeight: 750,
          fontSize: "1.45rem",
          lineHeight: 1.2,
          letterSpacing: "-0.015em",
        },
        h6: {
          fontWeight: 750,
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
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontWeight: 700,
        },
        button: {
          textTransform: "none",
          letterSpacing: "0.01em",
          fontWeight: 700,
          fontSize: "0.8125rem",
        },
      },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              backgroundColor: "var(--app-bg)",
              color: "var(--app-fg)",
              textRendering: "optimizeLegibility",
            },
          },
        },
        MuiCard: {
          variants: [
            {
              props: { variant: "outlined" },
              style: {
                borderRadius: 0,
                borderColor: "var(--app-border)",
                backgroundColor: "var(--app-surface)",
                boxShadow: "0 14px 40px rgba(15, 23, 42, 0.06)",
              },
            },
          ],
        },
        MuiCardContent: {
          styleOverrides: {
            root: {
              padding: 24,
              "&:last-child": {
                paddingBottom: 24,
              },
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
              borderRadius: 0,
              minHeight: 36,
              boxShadow: "none",
            },
          },
        },
        MuiToggleButton: {
          styleOverrides: {
            root: {
              borderRadius: 0,
              borderColor: "var(--app-control-border)",
              backgroundColor: "var(--app-control-bg)",
              color: "var(--app-muted)",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.01em",
              textTransform: "none",
              "&.Mui-selected": {
                borderColor: "var(--app-accent)",
                backgroundColor: "var(--app-control-active-bg)",
                color: "var(--app-fg)",
              },
              "&.Mui-selected:hover": {
                backgroundColor: "var(--app-control-active-bg)",
              },
              "&:hover": {
                backgroundColor: "var(--app-hover-bg)",
              },
            },
          },
        },
        MuiDialog: {
          styleOverrides: {
            paper: {
              borderRadius: 0,
              border: "1px solid var(--app-border)",
              backgroundColor: "var(--app-surface)",
              backgroundImage: "none",
              boxShadow: "0 24px 70px rgba(15, 23, 42, 0.22)",
            },
          },
        },
        MuiDialogTitle: {
          styleOverrides: {
            root: {
              color: "var(--app-fg)",
              fontWeight: 750,
            },
          },
        },
        MuiAlert: {
          styleOverrides: {
            root: {
              borderRadius: 0,
              border: "1px solid var(--app-border)",
              boxShadow: "none",
            },
          },
        },
        MuiDivider: {
          styleOverrides: {
            root: {
              borderColor: "var(--app-border)",
            },
          },
        },
        MuiCardActionArea: {
          styleOverrides: {
            root: {
              borderRadius: 0,
              "&:hover": {
                backgroundColor: "var(--app-hover-bg)",
              },
            },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: {
              borderRadius: 0,
              fontWeight: 700,
              letterSpacing: "0.01em",
              textTransform: "none",
            },
            outlined: {
              borderColor: "var(--app-control-border)",
            },
          },
        },
        MuiTabs: {
          styleOverrides: {
            root: {
              minHeight: 44,
            },
            indicator: {
              backgroundColor: "var(--app-accent)",
              borderRadius: 0,
              height: 3,
            },
          },
        },
        MuiTab: {
          styleOverrides: {
            root: {
              minHeight: 44,
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.01em",
              textTransform: "none",
              color: "var(--app-muted)",
              "&.Mui-selected": {
                color: "var(--app-fg)",
              },
            },
          },
        },
        MuiTooltip: {
          styleOverrides: {
            tooltip: {
              backgroundColor: "var(--app-fg)",
              color: "var(--app-bg)",
              border: "1px solid var(--app-border)",
              boxShadow: "0 18px 48px rgba(15, 23, 42, 0.18)",
              borderRadius: 0,
              fontSize: 12,
              lineHeight: 1.45,
            },
            arrow: {
              color: "var(--app-fg)",
            },
          },
        },
        MuiPopover: {
          styleOverrides: {
            paper: {
              borderRadius: 0,
              border: "1px solid var(--app-border)",
              boxShadow: "0 22px 60px rgba(15, 23, 42, 0.16)",
              backgroundImage: "none",
            },
          },
        },
        MuiMenu: {
          styleOverrides: {
            paper: {
              backgroundColor: "var(--app-surface)",
              color: "var(--app-fg)",
              border: "1px solid var(--app-border)",
            },
          },
        },
        MuiOutlinedInput: {
          styleOverrides: {
            root: {
              backgroundColor: "var(--app-control-bg)",
              borderRadius: 0,
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "var(--app-control-border)",
              },
              "&:hover .MuiOutlinedInput-notchedOutline": {
                borderColor: "var(--app-control-border)",
              },
              "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                borderColor: "var(--app-accent)",
                boxShadow: "0 0 0 3px var(--app-control-active-bg)",
              },
            },
            input: {
              color: "var(--app-fg)",
            },
          },
        },
        MuiInputLabel: {
          styleOverrides: {
            root: {
              color: "var(--app-muted)",
              "&.Mui-focused": {
                color: "var(--app-fg)",
              },
            },
          },
        },
        MuiFormHelperText: {
          styleOverrides: {
            root: {
              color: "var(--app-muted)",
            },
          },
        },
        MuiTableHead: {
          styleOverrides: {
            root: {
              "& .MuiTableCell-root": {
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.01em",
                textTransform: "none",
                color: "var(--app-muted)",
                borderBottomColor: "var(--app-border)",
              },
            },
          },
        },
        MuiTableCell: {
          styleOverrides: {
            root: {
              borderBottomColor: "var(--app-border)",
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


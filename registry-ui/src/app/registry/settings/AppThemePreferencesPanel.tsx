"use client";

import { APP_THEMES, type AppThemeId } from "@/lib/appThemes";
import { useAppTheme } from "@/hooks/useAppTheme";
import { Box, Card, CardContent, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";

export function AppThemePreferencesPanel() {
  const { themeId, setThemeId } = useAppTheme();

  return (
    <Card
      variant="outlined"
      component="section"
      sx={{
        borderRadius: 4,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            Appearance
          </Typography>
          <Typography variant="body2" sx={{ maxWidth: 720, color: "var(--app-muted)" }}>
            Sets the registry chrome theme (top bar, sidebar, and footer). Terminal color profiles are configured
            separately below. Use{" "}
            <Box component="kbd" sx={{ borderRadius: 1, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", px: 0.75, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 11 }}>
              Ctrl
            </Box>{" "}
            +{" "}
            <Box component="kbd" sx={{ borderRadius: 1, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", px: 0.75, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 11 }}>
              Shift
            </Box>{" "}
            +{" "}
            <Box component="kbd" sx={{ borderRadius: 1, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", px: 0.75, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 11 }}>
              C
            </Box>{" "}
            to toggle{" "}
            <Box component="strong" sx={{ color: "var(--app-fg)" }}>
              Navy Command
            </Box>{" "}
            and{" "}
            <Box component="strong" sx={{ color: "var(--app-fg)" }}>
              Paper Contrast
            </Box>
            .
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          <FormControl fullWidth size="small">
            <InputLabel id="settings-app-theme-label">Application theme</InputLabel>
            <Select
              labelId="settings-app-theme-label"
              id="settings-app-theme"
              label="Application theme"
              value={themeId}
              onChange={(e) => setThemeId(e.target.value as AppThemeId)}
            >
              {APP_THEMES.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.label} — {t.description}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Controls registry UI surfaces and accents
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}


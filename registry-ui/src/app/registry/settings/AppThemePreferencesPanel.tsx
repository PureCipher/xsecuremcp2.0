"use client";

import { APP_THEMES, type AppThemeId } from "@/lib/appThemes";
import { useAppTheme } from "@/hooks/useAppTheme";
import { Box, Card, CardContent, Chip, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";

export function AppThemePreferencesPanel() {
  const { themeId, setThemeId } = useAppTheme();

  return (
    <Card variant="outlined" component="section" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: { xs: 2, md: 2.5 } }}>
        <Box component="header" sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, justifyContent: "space-between", gap: 1.5 }}>
          <Box sx={{ display: "grid", gap: 0.5, maxWidth: 720 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Appearance
            </Typography>
            <Typography sx={{ fontSize: 15, fontWeight: 800, color: "var(--app-fg)" }}>
              Registry interface theme
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Sets navigation, surfaces, and accents for this browser. CLI terminal color profiles can be changed directly from the CLI page.
            </Typography>
          </Box>
          <Chip label="Ctrl + Shift + C toggles theme" sx={{ alignSelf: { xs: "flex-start", md: "center" }, bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
        </Box>

        <Box sx={{ mt: 2.25, display: "grid", gap: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel id="settings-app-theme-label">Application theme</InputLabel>
            <Select
              labelId="settings-app-theme-label"
              id="settings-app-theme"
              label="Application theme"
              value={themeId}
              onChange={(e) => setThemeId(e.target.value as AppThemeId)}
            >
              {APP_THEMES.map((theme) => (
                <MenuItem key={theme.id} value={theme.id}>
                  {theme.label} - {theme.description}
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


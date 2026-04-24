"use client";

import Link from "next/link";

import { useCliTerminalPreferences } from "@/hooks/useCliTerminalPreferences";
import { CLI_TERMINAL_THEMES } from "@/lib/cliTerminalThemes";
import { Box, Card, CardContent, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";

export function CliTerminalPreferencesPanel() {
  const { prefs, setThemeId, setFontSize, setFontFamily, setFontWeight, setFontWeightBold } =
    useCliTerminalPreferences();

  return (
    <Card
      variant="outlined"
      component="section"
      id="browser-cli-terminal"
      sx={{
        borderRadius: 4,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Browser CLI terminal
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, maxWidth: 720, color: "var(--app-muted)" }}>
          Preferences for the in-browser SecureMCP CLI on{" "}
          <Link href="/registry/cli" style={{ textDecoration: "underline", textDecorationColor: "var(--app-accent)" }}>
            <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", color: "var(--app-muted)" }}>
              /registry/cli
            </Box>
          </Link>
          . Stored in this browser only (
          <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
            localStorage
          </Box>
          ).
        </Typography>

        <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
          <Box>
            <FormControl fullWidth size="small">
              <InputLabel id="settings-cli-theme-label">Color profile</InputLabel>
              <Select
                labelId="settings-cli-theme-label"
                id="settings-cli-theme"
                label="Color profile"
                value={prefs.themeId}
                onChange={(e) => setThemeId(e.target.value)}
              >
                {CLI_TERMINAL_THEMES.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.label} — {t.description}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
              Background & text — Terminal.app-style presets
            </Typography>
          </Box>

          <Box>
            <FormControl fullWidth size="small">
              <InputLabel id="settings-cli-font-label">Monospace font size</InputLabel>
              <Select
                labelId="settings-cli-font-label"
                id="settings-cli-font"
                label="Monospace font size"
                value={String(prefs.fontSize)}
                onChange={(e) => setFontSize(Number(e.target.value))}
              >
                {[10, 11, 12, 13, 14, 15, 16, 18].map((n) => (
                  <MenuItem key={n} value={String(n)}>
                    {n}px
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
              xterm font size (px)
            </Typography>
          </Box>
        </Box>

        <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" } }}>
          <Box>
            <FormControl fullWidth size="small">
              <InputLabel id="settings-cli-font-family-label">Font</InputLabel>
              <Select
                labelId="settings-cli-font-family-label"
                id="settings-cli-font-family"
                label="Font"
                value={prefs.fontFamily}
                onChange={(e) => setFontFamily(e.target.value)}
              >
                {["JetBrains Mono", "Fira Code", "IBM Plex Mono", "Source Code Pro", "ui-monospace"].map((name) => (
                  <MenuItem key={name} value={name}>
                    {name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
              Font family (regular + bold)
            </Typography>
          </Box>

          <Box>
            <FormControl fullWidth size="small">
              <InputLabel id="settings-cli-font-weight-label">Weight (regular)</InputLabel>
              <Select
                labelId="settings-cli-font-weight-label"
                id="settings-cli-font-weight"
                label="Weight (regular)"
                value={prefs.fontWeight}
                onChange={(e) => setFontWeight(e.target.value as "normal" | "bold")}
              >
                <MenuItem value="normal">Regular</MenuItem>
                <MenuItem value="bold">Bold</MenuItem>
              </Select>
            </FormControl>
            <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
              Normal text weight
            </Typography>
          </Box>

          <Box>
            <FormControl fullWidth size="small">
              <InputLabel id="settings-cli-font-weight-bold-label">Weight (bold)</InputLabel>
              <Select
                labelId="settings-cli-font-weight-bold-label"
                id="settings-cli-font-weight-bold"
                label="Weight (bold)"
                value={prefs.fontWeightBold}
                onChange={(e) => setFontWeightBold(e.target.value as "normal" | "bold")}
              >
                <MenuItem value="bold">Bold</MenuItem>
                <MenuItem value="normal">Regular</MenuItem>
              </Select>
            </FormControl>
            <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
              Bold text weight
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

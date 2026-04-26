"use client";

import { useCallback, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { Box, Typography } from "@mui/material";

import { useCliTerminalPreferences } from "@/hooks/useCliTerminalPreferences";
import { CLI_TERMINAL_THEMES, getCliTerminalTheme } from "@/lib/cliTerminalThemes";

import { CliCheatsheet } from "./CliCheatsheet";
import { SecureCliTerminal } from "./SecureCliTerminal";

type Tab = { id: string; label: string };

type SessionState = { tabs: Tab[]; activeId: string };

function newSessionLabel(index: number) {
  return `Session ${index}`;
}

function initialSession(): SessionState {
  const id = "session-1";
  return { tabs: [{ id, label: newSessionLabel(1) }], activeId: id };
}

type Props = {
  defaultMcpUrl: string;
  allowedOrigin: string;
};

export function CliDeveloperWorkspace({ defaultMcpUrl, allowedOrigin }: Props) {
  const { prefs, setThemeId, setFontSize } = useCliTerminalPreferences();
  const theme = useMemo(() => getCliTerminalTheme(prefs.themeId), [prefs.themeId]);

  const [session, setSession] = useState<SessionState>(initialSession);

  const addTab = useCallback(() => {
    setSession((s) => {
      const id = crypto.randomUUID();
      return {
        tabs: [...s.tabs, { id, label: newSessionLabel(s.tabs.length + 1) }],
        activeId: id,
      };
    });
  }, []);

  const closeTab = useCallback((id: string) => {
    setSession((s) => {
      if (s.tabs.length <= 1) return s;
      const idx = s.tabs.findIndex((t) => t.id === id);
      const tabs = s.tabs.filter((t) => t.id !== id);
      let activeId = s.activeId;
      if (id === s.activeId) {
        const fb = tabs[Math.max(0, idx - 1)] ?? tabs[0];
        activeId = fb!.id;
      }
      return { tabs, activeId };
    });
  }, []);

  const { tabs, activeId } = session;
  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0]!;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box
        component="header"
        sx={{
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          alignItems: { xs: "flex-start", md: "flex-end" },
          justifyContent: "space-between",
          gap: 2,
        }}
      >
        <Box sx={{ display: "grid", gap: 0.75, maxWidth: 820 }}>
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            Developer access
          </Typography>
          <Typography variant="h5" sx={{ color: "var(--app-fg)" }}>
            SecureMCP CLI
          </Typography>
          <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
            A focused MCP terminal workspace inspired by Termius: sessions on the side, connection details up top, and quick commands close by.
          </Typography>
        </Box>

        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <WorkspaceChip label="Endpoint" value={defaultMcpUrl.replace(/^https?:\/\//, "")} />
          <WorkspaceChip label="Profile" value={theme.macStyle} />
        </Box>
      </Box>

      <Box
        sx={{
          display: "grid",
          minHeight: { xs: "auto", lg: "clamp(720px, calc(100vh - 8rem), 920px)" },
          gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1fr) 300px" },
          gap: 1.5,
          alignItems: "stretch",
        }}
      >
        <Box
          sx={{
            display: "grid",
            minWidth: 0,
            minHeight: { xs: 620, lg: "100%" },
            gridTemplateColumns: { xs: "1fr", md: "176px minmax(0, 1fr)" },
            overflow: "hidden",
            border: "1px solid var(--app-border)",
            borderRadius: 0,
            bgcolor: "var(--app-surface)",
            boxShadow: "0 18px 46px rgba(15, 23, 42, 0.10)",
          }}
        >
          <Box
            component="aside"
            sx={{
              display: { xs: "none", md: "flex" },
              flexDirection: "column",
              gap: 1.5,
              p: 1.5,
              borderRight: "1px solid var(--app-border)",
              bgcolor: "var(--app-control-bg)",
            }}
          >
            <Box>
              <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Sessions
              </Typography>
              <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                Stateful shells.
              </Typography>
            </Box>

            <Box sx={{ display: "grid", gap: 1 }}>
              {tabs.map((tab) => {
                const active = tab.id === activeId;
                return (
                  <Box
                    key={tab.id}
                    sx={{
                      width: "100%",
                      display: "flex",
                      alignItems: "stretch",
                      border: "1px solid",
                      borderColor: active ? "var(--app-accent)" : "var(--app-control-border)",
                      borderRadius: 0,
                      bgcolor: active ? "var(--app-control-active-bg)" : "var(--app-surface)",
                      color: active ? "var(--app-fg)" : "var(--app-muted)",
                      overflow: "hidden",
                    }}
                  >
                    <Box
                      component="button"
                      type="button"
                      onClick={() => setSession((s) => ({ ...s, activeId: tab.id }))}
                      sx={{
                        flex: 1,
                        border: 0,
                        bgcolor: "transparent",
                        color: "inherit",
                        px: 1,
                        py: 1,
                        textAlign: "left",
                        cursor: "pointer",
                        "&:hover": { bgcolor: "var(--app-hover-bg)" },
                      }}
                    >
                      <Typography sx={{ fontSize: 12, fontWeight: 800 }}>{tab.label}</Typography>
                      <Typography sx={{ mt: 0.35, fontSize: 10, color: "var(--app-muted)" }}>
                        MCP shell
                      </Typography>
                    </Box>
                    {tabs.length > 1 ? (
                      <Box
                        component="button"
                        type="button"
                        aria-label={`Close ${tab.label}`}
                        onClick={() => closeTab(tab.id)}
                        sx={{
                          border: 0,
                          borderLeft: "1px solid var(--app-border)",
                          bgcolor: "transparent",
                          px: 1,
                          color: "var(--app-muted)",
                          cursor: "pointer",
                          "&:hover": { color: "#b91c1c", bgcolor: "rgba(239, 68, 68, 0.08)" },
                        }}
                      >
                        x
                      </Box>
                    ) : null}
                  </Box>
                );
              })}
            </Box>

            <Box
              component="button"
              type="button"
              onClick={addTab}
              sx={{
                border: "1px dashed var(--app-control-border)",
                borderRadius: 0,
                bgcolor: "transparent",
                color: "var(--app-muted)",
                px: 1.25,
                py: 1,
                textAlign: "left",
                cursor: "pointer",
                "&:hover": { borderColor: "var(--app-accent)", color: "var(--app-fg)", bgcolor: "var(--app-hover-bg)" },
              }}
            >
              <Typography sx={{ fontSize: 12, fontWeight: 800 }}>+ New session</Typography>
            </Box>

            <Box sx={{ mt: "auto", display: "grid", gap: 1 }}>
              <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Connection
              </Typography>
              <Typography sx={{ fontSize: 10, lineHeight: 1.6, color: "var(--app-muted)", wordBreak: "break-word" }}>
                {allowedOrigin}
              </Typography>
            </Box>
          </Box>

          <Box sx={{ display: "flex", minWidth: 0, minHeight: 0, flexDirection: "column" }}>
            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 1.5,
                px: { xs: 1.5, md: 2 },
                py: 1.25,
                borderBottom: "1px solid var(--app-border)",
                bgcolor: "var(--app-surface)",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ display: "flex", gap: 0.65 }} aria-hidden>
                  {["#ef4444", "#f59e0b", "#22c55e"].map((color) => (
                    <Box key={color} sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: color, opacity: 0.85 }} />
                  ))}
                </Box>
                <Box>
                  <Typography sx={{ fontSize: 13, fontWeight: 800, color: "var(--app-fg)" }}>
                    {activeTab.label}
                  </Typography>
                  <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                    Secure registry MCP shell
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                <ControlSelect
                  id="cli-theme"
                  label="Terminal theme"
                  value={prefs.themeId}
                  onChange={setThemeId}
                  options={CLI_TERMINAL_THEMES.map((terminalTheme) => ({ value: terminalTheme.id, label: terminalTheme.label }))}
                />
                <ControlSelect
                  id="cli-font"
                  label="Font size"
                  value={String(prefs.fontSize)}
                  onChange={(value) => setFontSize(Number(value))}
                  options={[10, 11, 12, 13, 14, 15, 16, 18].map((size) => ({ value: String(size), label: `${size}px` }))}
                  width={92}
                />
                <Box
                  component="span"
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    minHeight: 32,
                    border: "1px solid var(--app-control-border)",
                    borderRadius: 0,
                    px: 1.25,
                    fontSize: 11,
                    fontWeight: 800,
                    color: "var(--app-muted)",
                  }}
                >
                  Stored locally
                </Box>
              </Box>
            </Box>

            <Box
              sx={{
                display: { xs: "flex", md: "none" },
                gap: 1,
                overflowX: "auto",
                px: 2,
                py: 1,
                borderBottom: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
              }}
            >
              {tabs.map((tab) => {
                const active = tab.id === activeId;
                return (
                  <Box
                    key={tab.id}
                    sx={{
                      display: "flex",
                      overflow: "hidden",
                      border: "1px solid",
                      borderColor: active ? "var(--app-accent)" : "var(--app-control-border)",
                      borderRadius: 0,
                      bgcolor: active ? "var(--app-control-active-bg)" : "var(--app-surface)",
                      color: active ? "var(--app-fg)" : "var(--app-muted)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <Box
                      component="button"
                      type="button"
                      onClick={() => setSession((s) => ({ ...s, activeId: tab.id }))}
                      sx={{ border: 0, bgcolor: "transparent", color: "inherit", px: 1.5, py: 0.75, cursor: "pointer" }}
                    >
                      <Typography sx={{ fontSize: 12, fontWeight: 800 }}>{tab.label}</Typography>
                    </Box>
                    {tabs.length > 1 ? (
                      <Box
                        component="button"
                        type="button"
                        aria-label={`Close ${tab.label}`}
                        onClick={() => closeTab(tab.id)}
                        sx={{ border: 0, borderLeft: "1px solid var(--app-border)", bgcolor: "transparent", px: 0.75, color: "var(--app-muted)" }}
                      >
                        x
                      </Box>
                    ) : null}
                  </Box>
                );
              })}
              <Box component="button" type="button" onClick={addTab} sx={{ border: "1px dashed var(--app-control-border)", borderRadius: 0, bgcolor: "transparent", px: 1.25, color: "var(--app-muted)" }}>
                +
              </Box>
            </Box>

            <Box
              sx={{
                position: "relative",
                minHeight: { xs: 480, md: 0 },
                flex: 1,
                bgcolor: theme.xterm.background,
              }}
            >
              <Box
                sx={{
                  position: "absolute",
                  inset: 0,
                  overflow: "hidden",
                  bgcolor: theme.xterm.background,
                }}
              >
                {tabs.map((tab) => (
                  <Box
                    key={tab.id}
                    sx={{
                      position: "absolute",
                      inset: 0,
                      zIndex: tab.id === activeId ? 10 : 0,
                      opacity: tab.id === activeId ? 1 : 0,
                      pointerEvents: tab.id === activeId ? "auto" : "none",
                    }}
                    aria-hidden={tab.id !== activeId}
                  >
                    <SecureCliTerminal
                      key={`${tab.id}-${prefs.themeId}-${prefs.fontFamily}-${prefs.fontSize}`}
                      defaultMcpUrl={defaultMcpUrl}
                      theme={theme}
                      fontSize={prefs.fontSize}
                      fontFamily={prefs.fontFamily}
                      fontWeight={prefs.fontWeight}
                      fontWeightBold={prefs.fontWeightBold}
                      visible={tab.id === activeId}
                    />
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </Box>

        <CliCheatsheet defaultMcpUrl={defaultMcpUrl} allowedOrigin={allowedOrigin} className="xl:sticky xl:top-20" />
      </Box>

      <Box
        component="section"
        sx={{
          borderRadius: 0,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-surface)",
          p: { xs: 2, md: 2.5 },
        }}
      >
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Full Python CLI
        </Typography>
        <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)", lineHeight: 1.6 }}>
          For stdio, securemcp run, install recipes, and OAuth, use the local securemcp binary (`uv sync` in this repo).
        </Typography>
      </Box>
    </Box>
  );
}

function WorkspaceChip({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        display: "grid",
        gap: 0.25,
        minWidth: 120,
        border: "1px solid var(--app-border)",
        borderRadius: 0,
        bgcolor: "var(--app-surface)",
        px: 1.5,
        py: 1,
      }}
    >
      <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {label}
      </Typography>
      <Typography sx={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12, fontWeight: 750, color: "var(--app-fg)" }}>
        {value}
      </Typography>
    </Box>
  );
}

function ControlSelect({
  id,
  label,
  value,
  onChange,
  options,
  width = 180,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  width?: number;
}) {
  return (
    <Box component="label" htmlFor={id} sx={{ display: "grid", gap: 0.35 }}>
      <Typography sx={{ fontSize: 9, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {label}
      </Typography>
      <Box
        component="select"
        id={id}
        value={value}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)}
        sx={{
          width,
          height: 34,
          border: "1px solid var(--app-control-border)",
          borderRadius: 0,
          bgcolor: "var(--app-control-bg)",
          px: 1,
          color: "var(--app-fg)",
          fontSize: 12,
          outline: "none",
          "&:focus": { borderColor: "var(--app-accent)", boxShadow: "0 0 0 3px var(--app-control-active-bg)" },
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Box>
    </Box>
  );
}

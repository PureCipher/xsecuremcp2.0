"use client";

import { useCallback, useState, useTransition } from "react";

import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
} from "@mui/material";

import {
  setControlPlaneEnabled,
  type ControlPlaneEntry,
  type ControlPlaneStatusResponse,
} from "@/lib/registryClient";

type Props = {
  initialStatus: ControlPlaneStatusResponse | null;
};

const PLANE_LABELS: Record<string, string> = {
  contracts: "Contract Broker",
  consent: "Consent Graph",
  provenance: "Provenance Ledger",
  reflexive: "Reflexive Core",
};

function formatTimestamp(secondsSinceEpoch: number | undefined): string {
  if (!secondsSinceEpoch) return "—";
  return new Date(secondsSinceEpoch * 1000).toLocaleString();
}

export function ControlPlanesPanel({ initialStatus }: Props) {
  const [planes, setPlanes] = useState<ControlPlaneEntry[]>(
    initialStatus?.planes ?? [],
  );
  const [error, setError] = useState<string | null>(initialStatus?.error ?? null);
  const [pendingPlane, setPendingPlane] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const onToggle = useCallback(
    async (plane: string, nextEnabled: boolean) => {
      setError(null);
      setPendingPlane(plane);
      try {
        const result = await setControlPlaneEnabled(plane, nextEnabled);
        if (!result || result.error) {
          setError(result?.error ?? "Toggle failed.");
          return;
        }
        startTransition(() => {
          setPlanes(result.planes ?? []);
        });
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Toggle failed.");
      } finally {
        setPendingPlane(null);
      }
    },
    [],
  );

  if (!initialStatus) {
    return (
      <Alert severity="error">
        Could not load control-plane status. Reload the page or check
        your registry connection.
      </Alert>
    );
  }

  return (
    <Card variant="outlined">
      <CardContent>
        {error ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        ) : null}

        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Opt-in planes
        </Typography>
        <Typography sx={{ mt: 1, mb: 2, fontSize: 13, color: "var(--app-muted)" }}>
          Disabling a plane drops its in-memory state. Operators
          who want to retain plane state across toggles should run
          the registry with a SQLite persistence path so each
          plane&apos;s backend writes to disk; on re-enable, the plane
          reloads from there.
        </Typography>

        <Box sx={{ display: "grid", gap: 1.5 }}>
          {planes.map((entry) => {
            const isPending = pendingPlane === entry.plane;
            const label = PLANE_LABELS[entry.plane] ?? entry.plane;
            return (
              <Box
                key={entry.plane}
                sx={{
                  p: 2,
                  borderRadius: 2,
                  border: "1px solid var(--app-border)",
                  bgcolor: "var(--app-surface)",
                  display: "grid",
                  gap: 1.25,
                  gridTemplateColumns: { xs: "1fr", md: "1fr auto" },
                  alignItems: "center",
                }}
              >
                <Box>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
                    <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
                      {label}
                    </Typography>
                    <Chip
                      size="small"
                      label={entry.plane}
                      sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontFamily: "var(--font-geist-mono), monospace", fontSize: 10 }}
                    />
                    <Chip
                      size="small"
                      label={entry.enabled ? "active" : "disabled"}
                      sx={{
                        bgcolor: entry.enabled ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                        color: entry.enabled ? "var(--app-fg)" : "var(--app-muted)",
                        fontWeight: 700,
                        fontSize: 11,
                        border: entry.enabled ? undefined : "1px solid var(--app-border)",
                      }}
                    />
                  </Stack>
                  <Typography sx={{ mt: 0.75, fontSize: 12, color: "var(--app-muted)" }}>
                    {entry.description}
                  </Typography>
                  {entry.persisted ? (
                    <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)", fontFamily: "var(--font-geist-mono), monospace" }}>
                      last toggled by {entry.persisted.updated_by} on{" "}
                      {formatTimestamp(entry.persisted.updated_at)}
                    </Typography>
                  ) : (
                    <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                      no operator overrides — running with constructor default
                    </Typography>
                  )}
                </Box>

                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 1.25 }}>
                  {isPending ? <CircularProgress size={16} /> : null}
                  <FormControlLabel
                    control={
                      <Switch
                        checked={entry.enabled}
                        disabled={isPending}
                        onChange={(_, checked) => onToggle(entry.plane, checked)}
                      />
                    }
                    label={entry.enabled ? "Enabled" : "Disabled"}
                  />
                </Box>
              </Box>
            );
          })}
        </Box>

        <Divider sx={{ my: 2.5 }} />

        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
          Toggles here change both how the governance panels report
          each plane <em>and</em> whether the plane&apos;s middleware
          enforces on MCP traffic. Persistent across restart via the
          registry&apos;s SQLite store. All changes are logged in the
          admin audit feed.
        </Typography>
      </CardContent>
    </Card>
  );
}

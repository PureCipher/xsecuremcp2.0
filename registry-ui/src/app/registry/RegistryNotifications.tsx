"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, ButtonBase, Typography } from "@mui/material";

import { NavIcon } from "@/components/security";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";

type FeedItem = {
  id: number;
  created_at: string;
  event_kind: string;
  title: string;
  body: string;
  link_path?: string | null;
};

export function RegistryNotifications() {
  const { prefs } = useRegistryUserPreferences();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastSeenIso, setLastSeenIso] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const lastSeenKey = "purecipher.registry.notifications.last_seen_at";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/notifications?limit=40", { cache: "no-store" });
      const data = (await res.json()) as { items?: FeedItem[]; error?: string };
      if (!res.ok) {
        setError(data.error ?? `HTTP ${res.status}`);
        setItems([]);
        return;
      }
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setError("Could not load notifications.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(lastSeenKey);
      if (stored) setLastSeenIso(stored);
    } catch {
      // ignore (private mode / disabled storage)
    }
    void load();
    const id = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  const visibleItems = useMemo(
    () => items.filter((item) => notificationEnabled(item.event_kind, prefs.notifications)),
    [items, prefs.notifications],
  );

  const hasUnread = (() => {
    if (!visibleItems.length) return false;
    if (!lastSeenIso) return true;
    const lastSeen = Date.parse(lastSeenIso);
    if (Number.isNaN(lastSeen)) return true;
    return visibleItems.some((i) => {
      const ts = Date.parse(i.created_at);
      return !Number.isNaN(ts) && ts > lastSeen;
    });
  })();

  useEffect(() => {
    if (!open) return;
    function onDocMouseDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    void load();
    const nowIso = new Date().toISOString();
    setLastSeenIso(nowIso);
    try {
      window.localStorage.setItem(lastSeenKey, nowIso);
    } catch {
      // ignore
    }
  }, [open, load]);

  return (
    <Box ref={rootRef} sx={{ position: "relative" }}>
      <ButtonBase
        type="button"
        onClick={() => setOpen((v) => !v)}
        sx={{
          position: "relative",
          width: 36,
          height: 36,
          p: 0,
          border: "1px solid",
          borderColor: open ? "var(--app-accent)" : "var(--app-control-border)",
          borderRadius: 2.5,
          bgcolor: open ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
          color: open ? "var(--app-fg)" : "var(--app-muted)",
          boxShadow: "0 8px 20px rgba(15, 23, 42, 0.06)",
          transition: "background-color 160ms ease, border-color 160ms ease, color 160ms ease",
          "&:hover": { bgcolor: "var(--app-hover-bg)" },
        }}
        aria-label="Notifications"
        aria-expanded={open}
        title="Notifications"
      >
        <NavIcon name="notify" className="h-4 w-4" />
        {hasUnread ? (
          <Box
            component="span"
            sx={{
              position: "absolute",
              top: 4,
              right: 4,
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: "var(--app-accent)",
            }}
            aria-hidden
          />
        ) : null}
      </ButtonBase>

      {open ? (
        <Box
          role="dialog"
          aria-label="Notification list"
          sx={{
            position: "fixed",
            top: 52,
            right: { xs: 12, sm: 24 },
            zIndex: (theme) => theme.zIndex.modal,
            width: "min(calc(100vw - 2rem), 22rem)",
            py: 1,
            border: "1px solid var(--app-border)",
            borderRadius: 3,
            bgcolor: "var(--app-surface)",
            color: "var(--app-fg)",
            backgroundImage: "none",
            boxShadow: "0 22px 60px rgba(15, 23, 42, 0.18)",
            outline: "1px solid var(--app-surface-ring)",
            overflow: "hidden",
          }}
        >
          <Box sx={{ px: 1.5, pb: 1, borderBottom: "1px solid var(--app-border)" }}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Registry activity
            </Typography>
            <Typography sx={{ mt: 0.25, fontSize: 10, color: "var(--app-muted)" }}>
              Major listing and policy events for your role.
            </Typography>
          </Box>
          <Box sx={{ maxHeight: "min(70vh, 20rem)", overflowY: "auto", px: 0.5, py: 0.5 }}>
            {loading && visibleItems.length === 0 ? (
              <Typography sx={{ px: 1.5, py: 2, fontSize: 11, color: "var(--app-muted)" }}>Loading...</Typography>
            ) : null}
            {error ? (
              <Typography sx={{ px: 1.5, py: 1.5, fontSize: 11, color: "#b91c1c" }}>{error}</Typography>
            ) : null}
            {!loading && !error && visibleItems.length === 0 ? (
              <Typography sx={{ px: 1.5, py: 2, fontSize: 11, color: "var(--app-muted)" }}>No enabled notifications yet.</Typography>
            ) : null}
            <Box component="ul" sx={{ display: "grid", gap: 0.5, m: 0, p: 0, listStyle: "none" }}>
              {visibleItems.map((item) => (
                <li key={`${item.id}-${item.created_at}`}>
                  {item.link_path ? (
                    <Link
                      href={item.link_path}
                      onClick={() => setOpen(false)}
                      style={{ display: "block", textDecoration: "none", color: "inherit" }}
                    >
                      <Box sx={{ borderRadius: 2, px: 1.5, py: 1, textAlign: "left", "&:hover": { bgcolor: "var(--app-hover-bg)" } }}>
                        <NotificationRow item={item} />
                      </Box>
                    </Link>
                  ) : (
                    <Box sx={{ borderRadius: 2, px: 1.5, py: 1 }}>
                      <NotificationRow item={item} />
                    </Box>
                  )}
                </li>
              ))}
            </Box>
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}

function notificationEnabled(
  eventKind: string,
  prefs: {
    publishUpdates: boolean;
    reviewQueue: boolean;
    policyChanges: boolean;
    securityAlerts: boolean;
  },
): boolean {
  const kind = eventKind.toLowerCase();
  if (kind.includes("policy") || kind.includes("proposal") || kind.includes("promotion")) {
    return prefs.policyChanges;
  }
  if (kind.includes("security") || kind.includes("health") || kind.includes("revocation") || kind.includes("alert")) {
    return prefs.securityAlerts;
  }
  if (kind.includes("pending_review") || kind.includes("review_queue")) {
    return prefs.reviewQueue;
  }
  if (kind.includes("listing") || kind.includes("moderation") || kind.includes("publish")) {
    return prefs.publishUpdates;
  }
  return true;
}

function NotificationRow({ item }: { item: FeedItem }) {
  const when = formatShortTime(item.created_at);
  return (
    <Box>
      <Typography sx={{ fontSize: 11, fontWeight: 700, color: "var(--app-fg)" }}>{item.title}</Typography>
      <Typography sx={{ mt: 0.25, fontSize: 10, lineHeight: 1.55, color: "var(--app-muted)" }}>
        {item.body}
      </Typography>
      <Typography sx={{ mt: 0.75, fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {when} / {item.event_kind.replace(/_/g, " ")}
      </Typography>
    </Box>
  );
}

function formatShortTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

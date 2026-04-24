"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { NavIcon } from "@/components/security";

type FeedItem = {
  id: number;
  created_at: string;
  event_kind: string;
  title: string;
  body: string;
  link_path?: string | null;
};

export function RegistryNotifications() {
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

  const hasUnread = (() => {
    if (!items.length) return false;
    if (!lastSeenIso) return true;
    const lastSeen = Date.parse(lastSeenIso);
    if (Number.isNaN(lastSeen)) return true;
    return items.some((i) => {
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
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`relative inline-flex items-center justify-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition ${
          open
            ? "border-[--app-accent] bg-[--app-control-active-bg] text-[--app-fg]"
            : "border-[--app-control-border] bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg]"
        }`}
        aria-label="Notifications"
        aria-expanded={open}
        title="Notifications"
      >
        <NavIcon name="notify" className="h-4 w-4" />
        {hasUnread ? (
          <span
            className="absolute right-0.5 top-0.5 h-2 w-2 rounded-full bg-[--app-accent]"
            aria-hidden
          />
        ) : null}
      </button>

      {open ? (
        <div
          className="absolute right-0 z-[60] mt-2 w-[min(100vw-2rem,22rem)] rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] py-2 shadow-lg ring-1 ring-[--app-surface-ring]"
          role="dialog"
          aria-label="Notification list"
        >
          <div className="border-b border-[--app-border] px-3 pb-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Registry activity
            </p>
            <p className="text-[10px] text-[--app-muted]">
              Major listing and policy events for your role.
            </p>
          </div>
          <div className="max-h-[min(70vh,20rem)] overflow-y-auto px-1 py-1">
            {loading && items.length === 0 ? (
              <p className="px-3 py-4 text-[11px] text-[--app-muted]">Loading…</p>
            ) : null}
            {error ? (
              <p className="px-3 py-3 text-[11px] text-red-600 dark:text-red-400">{error}</p>
            ) : null}
            {!loading && !error && items.length === 0 ? (
              <p className="px-3 py-4 text-[11px] text-[--app-muted]">No notifications yet.</p>
            ) : null}
            <ul className="grid gap-1">
              {items.map((item) => (
                <li key={`${item.id}-${item.created_at}`}>
                  {item.link_path ? (
                    <Link
                      href={item.link_path}
                      onClick={() => setOpen(false)}
                      className="block rounded-xl px-3 py-2 text-left transition hover:bg-[--app-hover-bg]"
                    >
                      <NotificationRow item={item} />
                    </Link>
                  ) : (
                    <div className="rounded-xl px-3 py-2">
                      <NotificationRow item={item} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function NotificationRow({ item }: { item: FeedItem }) {
  const when = formatShortTime(item.created_at);
  return (
    <div>
      <p className="text-[11px] font-semibold text-[--app-fg]">{item.title}</p>
      <p className="mt-0.5 line-clamp-3 text-[10px] leading-relaxed text-[--app-muted]">
        {item.body}
      </p>
      <p className="mt-1 text-[9px] uppercase tracking-[0.14em] text-[--app-muted]">
        {when} · {item.event_kind.replace(/_/g, " ")}
      </p>
    </div>
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

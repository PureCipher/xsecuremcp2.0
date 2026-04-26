"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useEffect, useMemo, useState } from "react";

export const REGISTRY_USER_PREFERENCES_STORAGE_KEY = "purecipher.registry.userPreferences.v1";
const CHANGE_EVENT = "purecipher-registry-user-preferences";
const SERVER_SYNC_EVENT = "purecipher-registry-user-preferences-server-sync";

export type RegistryUserPreferences = {
  notifications: {
    publishUpdates: boolean;
    reviewQueue: boolean;
    policyChanges: boolean;
    securityAlerts: boolean;
  };
  workspace: {
    defaultLandingPage: string;
    density: "comfortable" | "compact";
  };
  publisher: {
    defaultCertification: "basic" | "standard" | "advanced";
    openMineFirst: boolean;
  };
  reviewer: {
    defaultLane: "pending" | "approved" | "rejected";
    highRiskFirst: boolean;
  };
  admin: {
    defaultAdminView: "health" | "policy" | "settings";
    requireConfirmations: boolean;
  };
};

const DEFAULT_PREFERENCES: RegistryUserPreferences = {
  notifications: {
    publishUpdates: true,
    reviewQueue: true,
    policyChanges: true,
    securityAlerts: true,
  },
  workspace: {
    defaultLandingPage: "/registry/app",
    density: "comfortable",
  },
  publisher: {
    defaultCertification: "basic",
    openMineFirst: true,
  },
  reviewer: {
    defaultLane: "pending",
    highRiskFirst: true,
  },
  admin: {
    defaultAdminView: "health",
    requireConfirmations: true,
  },
};

function mergePreferences(value: Partial<RegistryUserPreferences> | null): RegistryUserPreferences {
  return {
    notifications: { ...DEFAULT_PREFERENCES.notifications, ...value?.notifications },
    workspace: { ...DEFAULT_PREFERENCES.workspace, ...value?.workspace },
    publisher: { ...DEFAULT_PREFERENCES.publisher, ...value?.publisher },
    reviewer: { ...DEFAULT_PREFERENCES.reviewer, ...value?.reviewer },
    admin: { ...DEFAULT_PREFERENCES.admin, ...value?.admin },
  };
}

function applyPreferencesToDocument(prefs: RegistryUserPreferences) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.registryDensity = prefs.workspace.density;
}

function parsePreferences(raw: string | null): RegistryUserPreferences {
  try {
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<RegistryUserPreferences>;
    return mergePreferences(parsed);
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function readPreferences(): RegistryUserPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  const prefs = parsePreferences(localStorage.getItem(REGISTRY_USER_PREFERENCES_STORAGE_KEY));
  applyPreferencesToDocument(prefs);
  return prefs;
}

function writePreferences(prefs: RegistryUserPreferences) {
  applyPreferencesToDocument(prefs);
  localStorage.setItem(REGISTRY_USER_PREFERENCES_STORAGE_KEY, JSON.stringify(prefs));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(CHANGE_EVENT, callback);
  };
}

function getSnapshot() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(REGISTRY_USER_PREFERENCES_STORAGE_KEY) ?? "";
}

export function useRegistryUserPreferences() {
  const rawSnapshot = useSyncExternalStore(
    subscribe,
    getSnapshot,
    () => "",
  );
  const prefs = useMemo(() => parsePreferences(rawSnapshot), [rawSnapshot]);
  const [serverStatus, setServerStatus] = useState<"idle" | "syncing" | "synced" | "local">("idle");
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    applyPreferencesToDocument(prefs);
  }, [prefs]);

  useEffect(() => {
    let cancelled = false;
    async function loadServerPreferences() {
      setServerStatus("syncing");
      setServerError(null);
      try {
        const response = await fetch("/api/me/preferences", { cache: "no-store" });
        const payload = (await response.json().catch(() => ({}))) as {
          preferences?: Partial<RegistryUserPreferences>;
          error?: string;
        };
        if (!response.ok || !payload.preferences) {
          throw new Error(payload.error ?? `Preferences unavailable (${response.status})`);
        }
        const merged = mergePreferences(payload.preferences);
        if (!cancelled) {
          writePreferences(merged);
          setServerStatus("synced");
        }
      } catch (error) {
        if (!cancelled) {
          setServerStatus("local");
          setServerError(error instanceof Error ? error.message : "Using local preferences.");
        }
      }
    }

    void loadServerPreferences();
    return () => {
      cancelled = true;
    };
  }, []);

  const setPrefs = useCallback((next: Partial<RegistryUserPreferences>) => {
    const current = readPreferences();
    const merged = mergePreferences({ ...current, ...next });
    writePreferences(merged);
    void syncPreferencesToServer(merged, setServerStatus, setServerError);
  }, []);

  const updateSection = useCallback(
    <K extends keyof RegistryUserPreferences>(
      section: K,
      next: Partial<RegistryUserPreferences[K]>,
    ) => {
      const current = readPreferences();
      const merged = mergePreferences({
        ...current,
        [section]: { ...current[section], ...next },
      });
      writePreferences(merged);
      void syncPreferencesToServer(merged, setServerStatus, setServerError);
    },
    [],
  );

  const resetPrefs = useCallback(() => {
    writePreferences(DEFAULT_PREFERENCES);
    void resetPreferencesOnServer(setServerStatus, setServerError);
  }, []);

  return { prefs, setPrefs, updateSection, resetPrefs, serverStatus, serverError };
}

async function syncPreferencesToServer(
  preferences: RegistryUserPreferences,
  setServerStatus: (status: "idle" | "syncing" | "synced" | "local") => void,
  setServerError: (error: string | null) => void,
) {
  setServerStatus("syncing");
  setServerError(null);
  try {
    const response = await fetch("/api/me/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferences }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      preferences?: Partial<RegistryUserPreferences>;
      error?: string;
    };
    if (!response.ok || !payload.preferences) {
      throw new Error(payload.error ?? `Save failed (${response.status})`);
    }
    writePreferences(mergePreferences(payload.preferences));
    setServerStatus("synced");
    window.dispatchEvent(new Event(SERVER_SYNC_EVENT));
  } catch (error) {
    setServerStatus("local");
    setServerError(error instanceof Error ? error.message : "Saved locally only.");
  }
}

async function resetPreferencesOnServer(
  setServerStatus: (status: "idle" | "syncing" | "synced" | "local") => void,
  setServerError: (error: string | null) => void,
) {
  setServerStatus("syncing");
  setServerError(null);
  try {
    const response = await fetch("/api/me/preferences", { method: "DELETE" });
    const payload = (await response.json().catch(() => ({}))) as {
      preferences?: Partial<RegistryUserPreferences>;
      error?: string;
    };
    if (!response.ok || !payload.preferences) {
      throw new Error(payload.error ?? `Reset failed (${response.status})`);
    }
    writePreferences(mergePreferences(payload.preferences));
    setServerStatus("synced");
  } catch (error) {
    setServerStatus("local");
    setServerError(error instanceof Error ? error.message : "Reset locally only.");
  }
}

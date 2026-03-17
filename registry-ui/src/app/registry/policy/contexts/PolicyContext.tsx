"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

type BannerState = { tone: "success" | "error"; message: string } | null;

type PolicyContextValue = {
  banner: BannerState;
  busyKey: string | null;
  currentUsername: string | null;
  setBanner: (banner: BannerState) => void;
  setBusyKey: (key: string | null) => void;
  isLoading: (key: string) => boolean;
  clearBanner: () => void;
};

const PolicyContext = createContext<PolicyContextValue | null>(null);

export function PolicyProvider({
  currentUsername,
  children,
}: {
  currentUsername?: string | null;
  children: ReactNode;
}) {
  const [banner, setBanner] = useState<BannerState>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const isLoading = useCallback(
    (key: string) => busyKey === key,
    [busyKey],
  );

  const clearBanner = useCallback(() => setBanner(null), []);

  return (
    <PolicyContext value={{
      banner,
      busyKey,
      currentUsername: currentUsername ?? null,
      setBanner,
      setBusyKey,
      isLoading,
      clearBanner,
    }}>
      {children}
    </PolicyContext>
  );
}

export function usePolicyContext(): PolicyContextValue {
  const context = useContext(PolicyContext);
  if (!context) {
    throw new Error("usePolicyContext must be used within a PolicyProvider");
  }
  return context;
}

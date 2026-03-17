"use client";

import { useState } from "react";

export type PolicyTabKey =
  | "overview"
  | "live"
  | "proposals"
  | "versions"
  | "tools"
  | "migration";

export function useTabNavigation(defaultTab: PolicyTabKey = "overview") {
  const [activeTab, setActiveTab] = useState<PolicyTabKey>(defaultTab);
  return { activeTab, setActiveTab };
}

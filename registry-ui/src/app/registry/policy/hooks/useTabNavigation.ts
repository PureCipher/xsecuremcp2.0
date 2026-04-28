"use client";

import { useState } from "react";

// Iter 14.16 — split the legacy ``overview`` tab into ``catalog``
// (browse + install policy bundles) and ``metrics`` (analytics +
// trend history).
//
// Iter 14.17 — consolidate by workflow. The original ``live`` and
// ``tools`` tabs both answered "what's running right now" — they
// merge into ``now-live`` (sub-tabs: live chain, tools).
// ``versions`` and ``migration`` both answered "how does this
// change over time" — they merge into ``lifecycle`` (sub-tabs:
// versions, migration). No content removed; sub-tabs are managed
// inside :file:`TabGroup.tsx`.
export type PolicyTabKey =
  | "catalog"
  | "now-live"
  | "proposals"
  | "lifecycle"
  | "metrics";

export function useTabNavigation(defaultTab: PolicyTabKey = "catalog") {
  const [activeTab, setActiveTab] = useState<PolicyTabKey>(defaultTab);
  return { activeTab, setActiveTab };
}

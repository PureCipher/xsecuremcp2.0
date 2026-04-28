/**
 * Iter 14.16 — OverviewTab is deprecated.
 *
 * The previous Overview tab combined two unrelated workflows:
 * a *picking* surface (browse + install policy bundles) and a
 * *monitoring* surface (analytics + history). Iter 14.16 split
 * them into two top-level tabs:
 *
 * - :file:`CatalogTab.tsx` — the bundle gallery.
 * - :file:`MetricsTab.tsx` — the analytics dashboard.
 *
 * This file is kept only because the workspace doesn't allow
 * deletion mid-iteration. Nothing should import from it; both
 * concrete tabs are imported by ``PolicyManager.tsx`` directly.
 */

export {};

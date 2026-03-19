"use client";

import { useMemo, useState } from "react";

import type { InstallRecipe } from "@/lib/registryClient";
import { CopyButton, TabBar } from "@/components/security";

type TabKey = "quickstart" | "client" | "docker" | "verify" | "other";

type Props = {
  primaryRecipe: InstallRecipe | null;
  clientRecipes: InstallRecipe[];
  dockerRecipes: InstallRecipe[];
  verifyRecipes: InstallRecipe[];
  otherRecipes: InstallRecipe[];
};

export function RecipeTabs({
  primaryRecipe,
  clientRecipes,
  dockerRecipes,
  verifyRecipes,
  otherRecipes,
}: Props) {
  const tabs = useMemo(() => {
    const base: { key: TabKey; label: string; visible: boolean }[] = [
      { key: "quickstart", label: "Quickstart", visible: primaryRecipe != null },
      { key: "client", label: "Client", visible: clientRecipes.length > 0 },
      { key: "docker", label: "Docker", visible: dockerRecipes.length > 0 },
      { key: "verify", label: "Verify", visible: verifyRecipes.length > 0 },
      { key: "other", label: "Other", visible: otherRecipes.length > 0 },
    ];

    return base
      .filter((t) => t.visible)
      .map((t) => ({ key: t.key, label: t.label }));
  }, [primaryRecipe, clientRecipes.length, dockerRecipes.length, verifyRecipes.length, otherRecipes.length]);

  const [activeTab, setActiveTab] = useState<TabKey>(() => (tabs[0]?.key ?? "other"));

  const content = useMemo(() => {
    switch (activeTab) {
      case "quickstart":
        return primaryRecipe ? (
          <PrimaryRecipeCard recipe={primaryRecipe} />
        ) : (
          <EmptyPanel />
        );
      case "client":
        return <RecipeGrid recipes={clientRecipes} />;
      case "docker":
        return <RecipeGrid recipes={dockerRecipes} />;
      case "verify":
        return <RecipeGrid recipes={verifyRecipes} />;
      case "other":
      default:
        return <RecipeGrid recipes={otherRecipes} />;
    }
  }, [activeTab, primaryRecipe, clientRecipes, dockerRecipes, verifyRecipes, otherRecipes]);

  if (tabs.length === 0) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">Install recipes</h2>
        <p className="mt-2 text-[12px] text-[--app-muted]">
          This listing doesn&apos;t expose runtime recipes yet.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2 rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">Install recipes</h2>
          <span className="text-[10px] text-[--app-muted]">
            {tabs.length} section{tabs.length === 1 ? "" : "s"}
          </span>
        </div>
        <TabBar
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(key) => setActiveTab(key as TabKey)}
        />
        <div className="pt-2">{content}</div>
      </div>
    </section>
  );
}

function EmptyPanel() {
  return (
    <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
      <p className="text-[11px] text-[--app-muted]">No recipes available in this section.</p>
    </div>
  );
}

function PrimaryRecipeCard({ recipe }: { recipe: InstallRecipe }) {
  const title = recipe.title ?? "Quickstart";
  const content = recipe.content ?? "";

  return (
    <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12px] font-semibold text-[--app-fg]">{title}</p>
          <p className="mt-1 text-[11px] text-[--app-muted]">
            Copy/paste the command below to get running quickly.
          </p>
        </div>
        <CopyButton text={content} label="Copy" />
      </div>
      <pre className="mt-3 max-h-72 overflow-auto rounded-2xl bg-[--app-chrome-bg] p-3 text-[11px] leading-relaxed text-[--app-fg]">
        {content}
      </pre>
    </div>
  );
}

function RecipeGrid({ recipes }: { recipes: InstallRecipe[] }) {
  if (!recipes || recipes.length === 0) return <EmptyPanel />;

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {recipes.map((recipe) => {
        const title = recipe.title ?? recipe.recipe_id;
        const content = recipe.content ?? "";
        return (
          <article
            key={recipe.recipe_id}
            className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="min-w-0 truncate text-[12px] font-semibold text-[--app-fg]">{title}</h3>
              <CopyButton text={content} label="Copy" className="shrink-0" />
            </div>
            <pre className="max-h-48 overflow-auto rounded-xl bg-[--app-chrome-bg] p-2 text-[11px] leading-relaxed text-[--app-fg]">
              {content}
            </pre>
          </article>
        );
      })}
    </div>
  );
}


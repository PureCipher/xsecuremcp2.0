"use client";

import { useMemo, useState } from "react";

import type { InstallRecipe } from "@/lib/registryClient";
import { CopyButton, TabBar } from "@/components/security";
import { Box, Typography } from "@mui/material";

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
      <Box sx={{ borderRadius: 4, border: "1px solid var(--app-border)", bgcolor: "var(--app-surface)", p: 2.5, boxShadow: "none" }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Install recipes
        </Typography>
        <Typography variant="body2" sx={{ mt: 1, color: "var(--app-muted)" }}>
          This listing doesn&apos;t expose runtime recipes yet.
        </Typography>
      </Box>
    );
  }

  return (
    <Box component="section" sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 1,
          borderRadius: 4,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-surface)",
          p: 2.5,
          boxShadow: "none",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            Install recipes
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            {tabs.length} section{tabs.length === 1 ? "" : "s"}
          </Typography>
        </Box>
        <TabBar tabs={tabs} activeTab={activeTab} onTabChange={(key) => setActiveTab(key as TabKey)} />
        <Box sx={{ pt: 1 }}>{content}</Box>
      </Box>
    </Box>
  );
}

function EmptyPanel() {
  return (
    <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 2, boxShadow: "none" }}>
      <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
        No recipes available in this section.
      </Typography>
    </Box>
  );
}

function PrimaryRecipeCard({ recipe }: { recipe: InstallRecipe }) {
  const title = recipe.title ?? "Quickstart";
  const content = recipe.content ?? "";

  return (
    <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 2, boxShadow: "none" }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            {title}
          </Typography>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Copy/paste the command below to get running quickly.
          </Typography>
        </Box>
        <CopyButton text={content} label="Copy" />
      </Box>
      <Box
        component="pre"
        sx={{
          mt: 2,
          maxHeight: 288,
          overflow: "auto",
          borderRadius: 3,
          bgcolor: "var(--app-chrome-bg)",
          p: 1.5,
          fontSize: 11,
          lineHeight: 1.6,
          color: "var(--app-fg)",
        }}
      >
        {content}
      </Box>
    </Box>
  );
}

function RecipeGrid({ recipes }: { recipes: InstallRecipe[] }) {
  if (!recipes || recipes.length === 0) return <EmptyPanel />;

  return (
    <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr", xl: "1fr 1fr 1fr" } }}>
      {recipes.map((recipe) => {
        const title = recipe.title ?? recipe.recipe_id;
        const content = recipe.content ?? "";
        return (
          <Box
            component="article"
            key={recipe.recipe_id}
            sx={{
              display: "flex",
              flexDirection: "column",
              gap: 1,
              borderRadius: 3,
              border: "1px solid var(--app-border)",
              bgcolor: "var(--app-control-bg)",
              p: 2,
              boxShadow: "none",
            }}
          >
            <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
              <Typography
                variant="body2"
                sx={{ minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 700, color: "var(--app-fg)" }}
              >
                {title}
              </Typography>
              <CopyButton text={content} label="Copy" className="shrink-0" />
            </Box>
            <Box
              component="pre"
              sx={{
                maxHeight: 192,
                overflow: "auto",
                borderRadius: 2.5,
                bgcolor: "var(--app-chrome-bg)",
                p: 1.25,
                fontSize: 11,
                lineHeight: 1.6,
                color: "var(--app-fg)",
              }}
            >
              {content}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}


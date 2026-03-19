export type AppThemeId = "emerald-forest" | "slate-night";

export type AppTheme = {
  id: AppThemeId;
  label: string;
  description: string;
};

export const DEFAULT_APP_THEME_ID: AppThemeId = "emerald-forest";

export const APP_THEMES: readonly AppTheme[] = [
  {
    id: "emerald-forest",
    label: "Emerald Forest",
    description: "PureCipher registry default — dark emerald chrome.",
  },
  {
    id: "slate-night",
    label: "Slate Night",
    description: "Neutral dark chrome with cool slate accents.",
  },
] as const;


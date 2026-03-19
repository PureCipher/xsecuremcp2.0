export type AppThemeId =
  | "emerald-forest"
  | "slate-night"
  | "amethyst-velvet"
  | "aurora-glacier"
  | "ember-noir"
  | "sandstone-day";

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
  {
    id: "amethyst-velvet",
    label: "Amethyst Velvet",
    description: "Deep violet chrome with bright amethyst accents.",
  },
  {
    id: "aurora-glacier",
    label: "Aurora Glacier",
    description: "Cool blue-green dark chrome with crisp cyan accents.",
  },
  {
    id: "ember-noir",
    label: "Ember Noir",
    description: "Charcoal chrome with ember orange accents.",
  },
  {
    id: "sandstone-day",
    label: "Sandstone Day",
    description: "Light warm surfaces with ink text and teal accents.",
  },
] as const;


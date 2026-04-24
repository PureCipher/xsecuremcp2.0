export type AppThemeId =
  | "navy-command"
  | "paper-contrast"
  | "emerald-forest"
  | "slate-night"
  | "amethyst-velvet"
  | "aurora-glacier"
  | "ember-noir"
  | "sandstone-day";

export const NAVY_COMMAND_THEME_ID = "navy-command" as const;
export const PAPER_CONTRAST_THEME_ID = "paper-contrast" as const;

export type AppTheme = {
  id: AppThemeId;
  label: string;
  description: string;
};

export const DEFAULT_APP_THEME_ID: AppThemeId = NAVY_COMMAND_THEME_ID;

export const APP_THEMES: readonly AppTheme[] = [
  {
    id: NAVY_COMMAND_THEME_ID,
    label: "Navy Command",
    description: "Deep navy chrome — default. Press Ctrl+Shift+C for paper contrast.",
  },
  {
    id: PAPER_CONTRAST_THEME_ID,
    label: "Paper Contrast",
    description: "White surfaces and black type. Toggle with Ctrl+Shift+C.",
  },
  {
    id: "emerald-forest",
    label: "Emerald Forest",
    description: "Dark emerald chrome with mint highlights.",
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

const THEME_ID_SET = new Set<string>(APP_THEMES.map((t) => t.id));

export function isAppThemeId(value: string): value is AppThemeId {
  return THEME_ID_SET.has(value);
}

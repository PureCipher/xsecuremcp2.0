import type { ITheme } from "@xterm/xterm";

const RESET = "\x1b[0m";

export type CliTerminalAnsi = {
  /** Prompt `$` color */
  prompt: string;
  /** Error lines */
  error: string;
  /** Welcome title accent */
  welcomeAccent: string;
  /** Welcome muted / labels */
  welcomeMuted: string;
};

export type CliTerminalTheme = {
  id: string;
  label: string;
  description: string;
  /** macOS / Terminal.app style hint */
  macStyle: string;
  xterm: ITheme;
  ansi: CliTerminalAnsi;
  /** Panel chrome (Tailwind ring) */
  ringClass: string;
};

function ansiFg256(n: number): string {
  return `\x1b[38;5;${n}m`;
}

function ansiFgRgb(r: number, g: number, b: number): string {
  return `\x1b[38;2;${r};${g};${b}m`;
}

export const CLI_TERMINAL_THEMES: CliTerminalTheme[] = [
  {
    id: "emerald-forest",
    label: "Emerald Forest",
    description: "PureCipher registry default — dark green console.",
    macStyle: "Custom (product)",
    xterm: {
      background: "#022c22",
      foreground: "#d1fae5",
      cursor: "#34d399",
      selectionBackground: "#065f46",
    },
    ansi: {
      prompt: ansiFgRgb(52, 211, 153),
      error: ansiFgRgb(251, 113, 133),
      welcomeAccent: ansiFgRgb(52, 211, 153),
      welcomeMuted: ansiFg256(245),
    },
    ringClass: "ring-emerald-800/80",
  },
  {
    id: "pro-dark",
    label: "Pro Dark",
    description: "Neutral dark — similar to Terminal “Pro” dark profiles.",
    macStyle: "Pro / Dark",
    xterm: {
      background: "#1e1e1e",
      foreground: "#d4d4d4",
      cursor: "#aeafad",
      selectionBackground: "#264f78",
    },
    ansi: {
      prompt: ansiFgRgb(78, 201, 176),
      error: ansiFgRgb(241, 76, 76),
      welcomeAccent: ansiFgRgb(100, 181, 246),
      welcomeMuted: ansiFg256(245),
    },
    ringClass: "ring-neutral-700/80",
  },
  {
    id: "homebrew",
    label: "Homebrew",
    description: "Classic green on black.",
    macStyle: "Homebrew",
    xterm: {
      background: "#000000",
      foreground: "#00ff00",
      cursor: "#00ff00",
      selectionBackground: "#003300",
    },
    ansi: {
      prompt: ansiFgRgb(0, 255, 0),
      error: ansiFgRgb(255, 85, 85),
      welcomeAccent: ansiFgRgb(57, 255, 20),
      welcomeMuted: ansiFg256(102),
    },
    ringClass: "ring-lime-900/70",
  },
  {
    id: "solarized-dark",
    label: "Solarized Dark",
    description: "Low-contrast dark palette.",
    macStyle: "Solarized Dark",
    xterm: {
      background: "#002b36",
      foreground: "#839496",
      cursor: "#93a1a1",
      selectionBackground: "#073642",
    },
    ansi: {
      prompt: ansiFgRgb(42, 161, 152),
      error: ansiFgRgb(220, 50, 47),
      welcomeAccent: ansiFgRgb(38, 139, 210),
      welcomeMuted: ansiFg256(245),
    },
    ringClass: "ring-cyan-900/60",
  },
  {
    id: "solarized-light",
    label: "Solarized Light",
    description: "Light workspace-friendly.",
    macStyle: "Solarized Light",
    xterm: {
      background: "#fdf6e3",
      foreground: "#657b83",
      cursor: "#586e75",
      selectionBackground: "#eee8d5",
    },
    ansi: {
      prompt: ansiFgRgb(42, 161, 152),
      error: ansiFgRgb(220, 50, 47),
      welcomeAccent: ansiFgRgb(38, 139, 210),
      welcomeMuted: ansiFg256(240),
    },
    ringClass: "ring-amber-200/50",
  },
  {
    id: "basic-light",
    label: "Basic Light",
    description: "Light gray background — Terminal “Basic” light feel.",
    macStyle: "Basic Light",
    xterm: {
      background: "#f5f5f5",
      foreground: "#1a1a1a",
      cursor: "#007aff",
      selectionBackground: "#c7e0ff",
    },
    ansi: {
      prompt: ansiFgRgb(0, 122, 255),
      error: ansiFgRgb(200, 0, 40),
      welcomeAccent: ansiFgRgb(0, 122, 255),
      welcomeMuted: ansiFg256(240),
    },
    ringClass: "ring-slate-300/80",
  },
  {
    id: "midnight-blue",
    label: "Midnight Blue",
    description: "Deep blue terminal popular in dev tools.",
    macStyle: "Ocean / Midnight",
    xterm: {
      background: "#0d1117",
      foreground: "#c9d1d9",
      cursor: "#58a6ff",
      selectionBackground: "#264f78",
    },
    ansi: {
      prompt: ansiFgRgb(63, 185, 80),
      error: ansiFgRgb(248, 81, 73),
      welcomeAccent: ansiFgRgb(88, 166, 255),
      welcomeMuted: ansiFg256(245),
    },
    ringClass: "ring-blue-900/70",
  },
];

export const DEFAULT_CLI_THEME_ID = "homebrew";

export function getCliTerminalTheme(id: string | undefined): CliTerminalTheme {
  const found = CLI_TERMINAL_THEMES.find((t) => t.id === id);
  return found ?? CLI_TERMINAL_THEMES[0]!;
}

export { RESET as CLI_ANSI_RESET };

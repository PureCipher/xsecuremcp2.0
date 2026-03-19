import { CLI_ANSI_RESET } from "@/lib/cliTerminalThemes";
import type { CliTerminalAnsi } from "@/lib/cliTerminalThemes";

/** Plain-text welcome for the in-browser CLI (no server / MCP imports). */

export function cliWelcomeLines(defaultMcpUrl: string, ansi: CliTerminalAnsi): string[] {
  const { welcomeAccent, welcomeMuted } = ansi;
  const R = CLI_ANSI_RESET;
  return [
    `${welcomeAccent}SecureMCP web CLI${R} — registry MCP session`,
    `${welcomeMuted}Default endpoint:${R} ${defaultMcpUrl}`,
    "",
    `${welcomeMuted}Try first:${R}  list          ${welcomeMuted}→ tools${R}`,
    `${welcomeMuted}          ${R}  list --prompts ${welcomeMuted}→ tools + prompts${R}`,
    `${welcomeMuted}          ${R}  call <tool>   ${welcomeMuted}→ invoke (same URL)${R}`,
    `${welcomeMuted}          ${R}  help          ${welcomeMuted}→ full reference${R}`,
    "",
    `${welcomeMuted}Keys:${R} ↑/↓ history · Ctrl+C clear line · ${welcomeMuted}clear${R} wipes screen`,
  ];
}

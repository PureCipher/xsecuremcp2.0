"use client";

import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import { useCallback, useEffect, useRef } from "react";

import "@xterm/xterm/css/xterm.css";

import type { CliTerminalTheme } from "@/lib/cliTerminalThemes";
import { CLI_ANSI_RESET } from "@/lib/cliTerminalThemes";

import { cliWelcomeLines } from "./cliWelcome";

type Props = {
  defaultMcpUrl: string;
  theme: CliTerminalTheme;
  fontSize: number;
  /** When true, terminal is on top and receives focus + fit */
  visible: boolean;
};

export function SecureCliTerminal({ defaultMcpUrl, theme, fontSize, visible }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const lineRef = useRef("");
  const historyRef = useRef<string[]>([]);
  const histPosRef = useRef(-1);
  const escSeqRef = useRef<"" | "\x1b" | "\x1b[">("");

  const prompt = useCallback(() => {
    const t = termRef.current;
    if (!t) return;
    const p = theme.ansi.prompt;
    const R = CLI_ANSI_RESET;
    t.write(`${p}$ ${R}`);
  }, [theme.ansi.prompt]);

  const runLine = useCallback(
    async (raw: string) => {
      const t = termRef.current;
      if (!t) return;
      const line = raw.trimEnd();
      const R = CLI_ANSI_RESET;
      const err = theme.ansi.error;
      if (line.length) {
        historyRef.current.push(line);
        if (historyRef.current.length > 200) historyRef.current.shift();
      }
      histPosRef.current = -1;

      if (line.toLowerCase() === "clear") {
        t.clear();
        for (const row of cliWelcomeLines(defaultMcpUrl, theme.ansi)) {
          t.writeln(row);
        }
        t.writeln("");
        prompt();
        return;
      }

      try {
        const res = await fetch("/api/cli/exec", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ line }),
        });
        const data = (await res.json()) as { ok: boolean; output?: string; error?: string };
        if (!data.ok) {
          t.writeln(`${err}${data.error ?? "Request failed"}${R}`);
        } else if (data.output) {
          t.writeln(data.output.replace(/\n/g, "\r\n"));
        }
      } catch {
        t.writeln(`${err}Network error calling /api/cli/exec${R}`);
      }
      t.writeln("");
      prompt();
    },
    [defaultMcpUrl, prompt, theme.ansi],
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const term = new Terminal({
      cursorBlink: true,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      fontSize,
      theme: theme.xterm,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(el);
    fit.fit();

    /** Must be set before `prompt()` — it reads `termRef.current`. */
    termRef.current = term;
    fitRef.current = fit;
    lineRef.current = "";

    for (const row of cliWelcomeLines(defaultMcpUrl, theme.ansi)) {
      term.writeln(row);
    }
    term.writeln("");
    prompt();

    const replaceCurrentLine = (entry: string) => {
      while (lineRef.current.length) {
        term.write("\b \b");
        lineRef.current = lineRef.current.slice(0, -1);
      }
      lineRef.current = entry;
      term.write(entry);
    };

    const onData = (data: string) => {
      const esc = escSeqRef.current;
      if (esc === "\x1b") {
        if (data === "[") {
          escSeqRef.current = "\x1b[";
          return;
        }
        escSeqRef.current = "";
      } else if (esc === "\x1b[") {
        escSeqRef.current = "";
        const h = historyRef.current;
        if (data === "A" && h.length) {
          if (histPosRef.current < 0) histPosRef.current = h.length - 1;
          else histPosRef.current = Math.max(0, histPosRef.current - 1);
          replaceCurrentLine(h[histPosRef.current] ?? "");
          return;
        }
        if (data === "B" && h.length) {
          if (histPosRef.current < 0) return;
          if (histPosRef.current >= h.length - 1) {
            histPosRef.current = -1;
            replaceCurrentLine("");
          } else {
            histPosRef.current += 1;
            replaceCurrentLine(h[histPosRef.current] ?? "");
          }
          return;
        }
      }

      if (data === "\x1b") {
        escSeqRef.current = "\x1b";
        return;
      }
      escSeqRef.current = "";

      if (data === "\r") {
        term.write("\r\n");
        const current = lineRef.current;
        lineRef.current = "";
        void runLine(current);
        return;
      }
      if (data === "\x7f" || data === "\b") {
        if (lineRef.current.length) {
          lineRef.current = lineRef.current.slice(0, -1);
          term.write("\b \b");
        }
        return;
      }
      if (data === "\x03") {
        lineRef.current = "";
        term.write("^C\r\n");
        prompt();
        return;
      }
      if (data >= " " && data.length === 1) {
        histPosRef.current = -1;
        lineRef.current += data;
        term.write(data);
      }
    };

    term.onData(onData);

    const ro = new ResizeObserver(() => {
      fit.fit();
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [defaultMcpUrl, fontSize, prompt, runLine, theme.ansi, theme.xterm]);

  useEffect(() => {
    const term = termRef.current;
    const fit = fitRef.current;
    if (!term || !fit || !visible) return;
    requestAnimationFrame(() => {
      fit.fit();
      term.focus();
    });
  }, [visible]);

  return (
    <div
      ref={containerRef}
      className={`h-full min-h-[320px] w-full overflow-hidden ring-1 ${theme.ringClass}`}
      style={{ backgroundColor: theme.xterm.background }}
      aria-label="SecureMCP CLI terminal"
    />
  );
}

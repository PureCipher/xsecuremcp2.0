"use client";

import {
  useState,
  useRef,
  useMemo,
  useCallback,
  useEffect,
  type KeyboardEvent,
  type UIEvent,
} from "react";
import { Box, Chip } from "@mui/material";

// ── Lightweight JSON syntax highlighter ──────────────────────────────
// Tokenizes JSON text and wraps each token in a <span> with inline styles.
// No external dependencies — just regex-based token matching.

export function highlightJson(text: string): string {
  const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  return escaped
    .replace(/("(?:[^"\\]|\\.)*")\s*:/g, '<span style="color: var(--app-muted);">$1</span>:')
    .replace(/:\s*("(?:[^"\\]|\\.)*")/g, ': <span style="color: rgb(253, 230, 138);">$1</span>')
    .replace(/(?<=[[,\s])("(?:[^"\\]|\\.)*")(?=[,\]\s])/g, '<span style="color: rgb(253, 230, 138);">$1</span>')
    .replace(/\b(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b/g, '<span style="color: rgb(125, 211, 252);">$1</span>')
    .replace(/\b(true|false|null)\b/g, '<span style="color: rgb(196, 181, 253);">$1</span>');
}

type ValidationResult = { valid: true } | { valid: false; message: string; position?: number };

function validateJson(text: string): ValidationResult {
  if (!text.trim()) return { valid: true };
  try {
    JSON.parse(text);
    return { valid: true };
  } catch (error) {
    if (error instanceof SyntaxError) {
      const posMatch = error.message.match(/position\s+(\d+)/i);
      return {
        valid: false,
        message: error.message.replace(/^JSON\.parse:\s*/, ""),
        position: posMatch ? Number(posMatch[1]) : undefined,
      };
    }
    return { valid: false, message: "Invalid JSON" };
  }
}

type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  minHeight?: string;
  placeholder?: string;
  hideValidation?: boolean;
};

export function JsonEditor({
  value,
  onChange,
  minHeight = "280px",
  placeholder,
  hideValidation = false,
}: JsonEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  const handleScroll = useCallback((event: UIEvent<HTMLTextAreaElement>) => {
    if (preRef.current) {
      preRef.current.scrollTop = event.currentTarget.scrollTop;
      preRef.current.scrollLeft = event.currentTarget.scrollLeft;
    }
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      const target = event.currentTarget;

      if (event.key === "Tab") {
        event.preventDefault();
        const start = target.selectionStart;
        const end = target.selectionEnd;
        const newValue = value.slice(0, start) + "  " + value.slice(end);
        onChange(newValue);
        requestAnimationFrame(() => {
          target.selectionStart = start + 2;
          target.selectionEnd = start + 2;
        });
      }

      if (event.key === "Enter") {
        const start = target.selectionStart;
        const lineStart = value.lastIndexOf("\n", start - 1) + 1;
        const line = value.slice(lineStart, start);
        const indent = line.match(/^(\s*)/)?.[1] ?? "";
        const charBefore = value[start - 1];
        const extra = charBefore === "{" || charBefore === "[" ? "  " : "";

        event.preventDefault();
        const newValue = value.slice(0, start) + "\n" + indent + extra + value.slice(start);
        onChange(newValue);
        requestAnimationFrame(() => {
          const pos = start + 1 + indent.length + extra.length;
          target.selectionStart = pos;
          target.selectionEnd = pos;
        });
      }
    },
    [value, onChange],
  );

  const highlighted = useMemo(() => highlightJson(value), [value]);
  const validation = useMemo(() => validateJson(value), [value]);

  useEffect(() => {
    if (textareaRef.current && preRef.current) {
      preRef.current.scrollTop = textareaRef.current.scrollTop;
      preRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, [value]);

  const hasContent = value.trim().length > 0;
  const showValidation = !hideValidation && hasContent;

  const borderColor =
    isFocused
      ? validation.valid || !hasContent
        ? "var(--app-accent)"
        : "rgba(251, 113, 133, 0.85)"
      : validation.valid || !hasContent
        ? "var(--app-border)"
        : "rgba(244, 63, 94, 0.75)";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <Box
        sx={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 3,
          border: "1px solid",
          borderColor,
          bgcolor: "var(--app-chrome-bg)",
          minHeight,
          transition: "border-color 120ms ease",
        }}
      >
        <Box
          component="pre"
          ref={preRef}
          aria-hidden="true"
          sx={{
            pointerEvents: "none",
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            whiteSpace: "pre-wrap",
            overflowWrap: "anywhere",
            px: 2,
            py: 1.5,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 12,
            lineHeight: 1.8,
            color: "var(--app-fg)",
            m: 0,
          }}
          dangerouslySetInnerHTML={{ __html: highlighted || "&nbsp;" }}
        />

        <Box
          component="textarea"
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onScroll={handleScroll}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          spellCheck={false}
          sx={{
            position: "relative",
            width: "100%",
            resize: "vertical",
            backgroundColor: "transparent",
            px: 2,
            py: 1.5,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize: 12,
            lineHeight: 1.8,
            color: "transparent",
            caretColor: "var(--app-fg)",
            outline: "none",
            border: "none",
            minHeight,
            "&::placeholder": { color: "var(--app-muted)", opacity: 1 },
            "&::selection": { backgroundColor: "var(--app-control-active-bg)", color: "transparent" },
          }}
        />
      </Box>

      {showValidation ? (
        <Chip
          size="small"
          label={validation.valid ? "Valid JSON" : validation.message}
          sx={{
            alignSelf: "flex-start",
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 700,
            bgcolor: validation.valid ? "var(--app-control-active-bg)" : "rgba(244, 63, 94, 0.12)",
            color: validation.valid ? "var(--app-muted)" : "rgb(254, 205, 211)",
            border: "1px solid",
            borderColor: validation.valid ? "var(--app-border)" : "rgba(251, 113, 133, 0.45)",
          }}
        />
      ) : null}
    </Box>
  );
}

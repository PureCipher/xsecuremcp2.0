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

// ── Lightweight JSON syntax highlighter ──────────────────────────────
// Tokenizes JSON text and wraps each token in a <span> with a color class.
// No external dependencies — just regex-based token matching.

export function highlightJson(text: string): string {
  // Escape HTML entities first
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Tokenize and colorize
  return escaped
    // Strings (keys and values)
    .replace(
      /("(?:[^"\\]|\\.)*")\s*:/g,
      '<span class="text-emerald-300">$1</span>:',
    )
    .replace(
      /:\s*("(?:[^"\\]|\\.)*")/g,
      ': <span class="text-amber-300">$1</span>',
    )
    // Standalone strings (in arrays, etc.)
    .replace(
      /(?<=[[,\s])("(?:[^"\\]|\\.)*")(?=[,\]\s])/g,
      '<span class="text-amber-300">$1</span>',
    )
    // Numbers
    .replace(
      /\b(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b/g,
      '<span class="text-sky-300">$1</span>',
    )
    // Booleans and null
    .replace(
      /\b(true|false|null)\b/g,
      '<span class="text-violet-300">$1</span>',
    );
}

// ── Validation ───────────────────────────────────────────────────────

type ValidationResult =
  | { valid: true }
  | { valid: false; message: string; position?: number };

function validateJson(text: string): ValidationResult {
  if (!text.trim()) return { valid: true };
  try {
    JSON.parse(text);
    return { valid: true };
  } catch (error) {
    if (error instanceof SyntaxError) {
      // Try to extract position from the error message
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

// ── Component ────────────────────────────────────────────────────────

type JsonEditorProps = {
  value: string;
  onChange: (value: string) => void;
  minHeight?: string;
  placeholder?: string;
  /** Hide the validation bar (e.g. for non-JSON textareas) */
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

  // Sync scroll between textarea and highlighted pre
  const handleScroll = useCallback((event: UIEvent<HTMLTextAreaElement>) => {
    if (preRef.current) {
      preRef.current.scrollTop = event.currentTarget.scrollTop;
      preRef.current.scrollLeft = event.currentTarget.scrollLeft;
    }
  }, []);

  // Auto-indent on Enter and handle Tab
  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      const target = event.currentTarget;

      if (event.key === "Tab") {
        event.preventDefault();
        const start = target.selectionStart;
        const end = target.selectionEnd;
        const newValue =
          value.slice(0, start) + "  " + value.slice(end);
        onChange(newValue);
        // Restore cursor position after React re-render
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

        // Add extra indent after { or [
        const extra = charBefore === "{" || charBefore === "[" ? "  " : "";

        event.preventDefault();
        const newValue =
          value.slice(0, start) + "\n" + indent + extra + value.slice(start);
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

  // Highlighted HTML
  const highlighted = useMemo(() => highlightJson(value), [value]);

  // Validation result
  const validation = useMemo(() => validateJson(value), [value]);

  // Keep scroll in sync on value changes
  useEffect(() => {
    if (textareaRef.current && preRef.current) {
      preRef.current.scrollTop = textareaRef.current.scrollTop;
      preRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, [value]);

  const hasContent = value.trim().length > 0;
  const showValidation = !hideValidation && hasContent;

  return (
    <div className="flex flex-col gap-1.5">
      {/* Editor container */}
      <div
        className={`relative overflow-hidden rounded-2xl border transition ${
          isFocused
            ? validation.valid || !hasContent
              ? "border-emerald-400"
              : "border-rose-400"
            : validation.valid || !hasContent
              ? "border-emerald-700/70"
              : "border-rose-500/70"
        } bg-emerald-950`}
        style={{ minHeight }}
      >
        {/* Syntax-highlighted layer (behind) */}
        <pre
          ref={preRef}
          className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words px-4 py-3 font-mono text-xs leading-6 text-emerald-50"
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: highlighted || "&nbsp;" }}
        />

        {/* Textarea layer (on top, transparent text) */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onScroll={handleScroll}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          spellCheck={false}
          className="relative w-full resize-y bg-transparent px-4 py-3 font-mono text-xs leading-6 text-transparent caret-emerald-50 outline-none selection:bg-emerald-500/30 selection:text-transparent placeholder:text-emerald-400/50"
          style={{ minHeight }}
        />
      </div>

      {/* Validation bar */}
      {showValidation ? (
        <div
          className={`flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-medium ${
            validation.valid
              ? "bg-emerald-500/10 text-emerald-300"
              : "bg-rose-500/10 text-rose-200"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              validation.valid ? "bg-emerald-400" : "bg-rose-400"
            }`}
          />
          {validation.valid
            ? "Valid JSON"
            : validation.message}
        </div>
      ) : null}
    </div>
  );
}

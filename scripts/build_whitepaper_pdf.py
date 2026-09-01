"""Render a repo-root Markdown white paper to a print-ready PDF.

Usage::

    uv run --with markdown --with weasyprint scripts/build_whitepaper_pdf.py [SOURCE.md]

``SOURCE.md`` defaults to ``SECUREMCP_WHITEPAPER.md``. The output names and the
running footer title are derived from it, so a new document needs no edits here.

Uses WeasyPrint's Python API rather than its CLI so the resolved
``pydyf``/``weasyprint`` pair always match (a Homebrew ``weasyprint`` paired
with a system ``pydyf`` can be version-skewed).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "SECUREMCP_WHITEPAPER.md")
HTML_OUT = ROOT / "artifacts" / f"{SOURCE.stem}.html"
PDF_OUT = ROOT / "artifacts" / f"{SOURCE.stem}.pdf"

# __RUNNING_TITLE__ is substituted with the document's own H1 in main().
# (Plain replace rather than str.format, since the CSS is full of braces.)
CSS = """
@page {
  size: A4;
  margin: 20mm 18mm 22mm 18mm;
  @bottom-center {
    content: counter(page);
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 8.5pt;
    color: #8a8f98;
  }
  @bottom-right {
    content: "__RUNNING_TITLE__";
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 7.5pt;
    color: #b0b5bd;
  }
}
@page :first {
  margin-top: 42mm;
  @bottom-center { content: ""; }
  @bottom-right { content: ""; }
}

html { font-size: 10.2pt; }
body {
  font-family: "Charter", "Georgia", "Times New Roman", serif;
  line-height: 1.52;
  color: #1c1e21;
  hyphens: auto;
}

h1, h2, h3, h4 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #0f1114;
  line-height: 1.22;
  break-after: avoid;
}
h1 {
  font-size: 25pt;
  letter-spacing: -0.4pt;
  margin: 0 0 6pt 0;
  padding-bottom: 10pt;
  border-bottom: 2.5pt solid #1c1e21;
}
h2 {
  font-size: 14pt;
  margin: 22pt 0 7pt 0;
  padding-bottom: 3pt;
  border-bottom: 0.6pt solid #d7dae0;
  break-before: auto;
}
h3 { font-size: 11.4pt; margin: 15pt 0 5pt 0; }
h4 { font-size: 10.2pt; margin: 12pt 0 4pt 0; color: #33373d; }

p { margin: 0 0 7.5pt 0; orphans: 2; widows: 2; }
strong { color: #0f1114; }

/* Title block: h1 → subtitle → descriptor. */
h1 + p {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 13pt;
  font-weight: 500;
  line-height: 1.35;
  color: #2b3038;
  margin-bottom: 9pt;
}
h1 + p strong { font-weight: 500; }
h1 + p + p {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.48;
  color: #6c727b;
  margin-bottom: 18pt;
}

ul, ol { margin: 0 0 8pt 0; padding-left: 17pt; }
li { margin-bottom: 3pt; }

code {
  font-family: "SF Mono", "Menlo", "Consolas", monospace;
  font-size: 8.6pt;
  background: #f2f3f5;
  padding: 0.5pt 2.5pt;
  border-radius: 2pt;
  color: #1f2328;
}
pre {
  background: #f7f8fa;
  border: 0.6pt solid #e1e4e9;
  border-left: 2.5pt solid #6b7280;
  border-radius: 3pt;
  padding: 8pt 10pt;
  margin: 0 0 9pt 0;
  break-inside: avoid;
  white-space: pre-wrap;
}
pre code {
  background: none;
  padding: 0;
  font-size: 8.1pt;
  line-height: 1.42;
  color: #24282e;
}

blockquote {
  margin: 9pt 0;
  padding: 7pt 11pt;
  background: #fbf8f1;
  border-left: 2.5pt solid #c99a3d;
  color: #3d3831;
  break-inside: avoid;
}
blockquote p { margin: 0 0 4pt 0; }
blockquote p:last-child { margin-bottom: 0; }

table {
  border-collapse: collapse;
  width: 100%;
  margin: 0 0 10pt 0;
  font-size: 8.9pt;
  break-inside: avoid;
}
th, td {
  border-bottom: 0.5pt solid #dfe2e7;
  padding: 4pt 6pt;
  text-align: left;
  vertical-align: top;
}
th {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 8.4pt;
  background: #f2f3f5;
  border-bottom: 1pt solid #b9bec6;
  color: #1c1e21;
}
tbody tr:nth-child(even) { background: #fafbfc; }

hr {
  border: none;
  border-top: 0.6pt solid #dfe2e7;
  margin: 18pt 0;
}

a { color: #1c1e21; text-decoration: none; }
em { color: #33373d; }
"""


def main() -> int:
    if not SOURCE.exists():
        print(f"error: {SOURCE} not found", file=sys.stderr)
        return 1

    text = SOURCE.read_text(encoding="utf-8")

    h1 = re.search(r"^#\s+(.+)$", text, flags=re.M)
    subtitle = re.search(r"^\*\*(.+?)\*\*\s*$", text, flags=re.M)
    running_title = h1.group(1).strip() if h1 else SOURCE.stem
    doc_title = running_title
    if subtitle:
        doc_title += f" — {subtitle.group(1).strip()}"

    # Drop the trailing attribution line; it belongs in the repo, not the PDF.
    text = re.sub(r"\n---\n\n\*🤖 Generated with.*$", "\n", text, flags=re.S)

    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )

    css = CSS.replace("__RUNNING_TITLE__", running_title)

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{doc_title}</title>"
        f"<style>{css}</style></head><body>{body}</body></html>"
    )

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html, encoding="utf-8")

    HTML(string=html, base_url=str(ROOT)).write_pdf(str(PDF_OUT))

    size_kb = PDF_OUT.stat().st_size / 1024
    print(f"wrote {PDF_OUT.relative_to(ROOT)} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

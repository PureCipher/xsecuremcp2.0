/**
 * Render a repo-root Markdown white paper to a formatted Word document.
 *
 * The Markdown is parsed rather than transcribed, so the .docx stays in sync
 * with the source file. Handles headings, paragraphs, fenced code, blockquotes,
 * bullet/ordered lists, pipe tables (with alignment), horizontal rules, and
 * inline bold/italic/code/links.
 *
 * Usage:
 *   npm install docx            # or: npm --prefix /tmp/docxbuild install docx
 *   node scripts/build_whitepaper_docx.js [SOURCE.md]
 *
 * SOURCE.md defaults to SECUREMCP_WHITEPAPER.md; the output name and the
 * running footer title are both derived from it, so a new document needs no
 * script changes.
 *
 * If `docx` is installed outside the repo, point NODE_PATH at it:
 *   NODE_PATH=/tmp/docxbuild/node_modules node scripts/build_whitepaper_docx.js
 */

"use strict";

const fs = require("fs");
const path = require("path");

const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TableOfContents,
  TextRun,
  WidthType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const SOURCE = path.resolve(ROOT, process.argv[2] || "SECUREMCP_WHITEPAPER.md");
const STEM = path.basename(SOURCE, ".md");
const OUT = path.join(ROOT, "artifacts", `${STEM}.docx`);

// The running footer title is the document's own H1, so retitling the source
// retitles the footer without touching this script.
const RUNNING_TITLE = (
  fs.readFileSync(SOURCE, "utf8").match(/^#\s+(.+)$/m)?.[1] ?? STEM
).trim();

// ── Typography ─────────────────────────────────────────────────────────
// Sizes are half-points. Fonts are chosen for cross-platform availability.
const BODY_FONT = "Georgia";
const HEAD_FONT = "Arial";
const MONO_FONT = "Consolas";

const SIZE_BODY = 21; // 10.5pt
const SIZE_CODE = 15; // 7.5pt — the widest code line is 108 chars; this fits
const SIZE_TABLE = 18; // 9pt
const SIZE_TABLE_HEAD = 17; // 8.5pt

const INK = "1C1E21";
const INK_SOFT = "4A5058";
const INK_FAINT = "6C727B";
const RULE = "D7DAE0";
const CODE_BG = "F7F8FA";
const INLINE_CODE_BG = "F2F3F5";
const TABLE_HEAD_BG = "F2F3F5";
const QUOTE_BG = "FBF8F1";
const QUOTE_BAR = "C99A3D";
const CODE_BAR = "6B7280";

// US Letter, 0.75" side margins → 10080 DXA of content width.
const PAGE_WIDTH = 12240;
const MARGIN_X = 1080;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2;

// ── Markdown → block list ──────────────────────────────────────────────

/**
 * Parse Markdown into a flat list of block descriptors.
 * @param {string} md
 * @returns {Array<object>}
 */
function parseBlocks(md) {
  const lines = md.split("\n");
  const blocks = [];
  let i = 0;

  const flushParagraph = (buf) => {
    if (buf.length) blocks.push({ type: "p", text: buf.join(" ").trim() });
    return [];
  };

  let para = [];

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code
    if (line.startsWith("```")) {
      para = flushParagraph(para);
      const lang = line.slice(3).trim();
      const body = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        body.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence
      blocks.push({ type: "code", lang, lines: body });
      continue;
    }

    // Heading
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      para = flushParagraph(para);
      blocks.push({
        type: `h${heading[1].length}`,
        text: heading[2].trim(),
      });
      i += 1;
      continue;
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line)) {
      para = flushParagraph(para);
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }

    // Table — a run of lines starting with '|'
    if (line.startsWith("|")) {
      para = flushParagraph(para);
      const raw = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        raw.push(lines[i]);
        i += 1;
      }
      blocks.push(parseTable(raw));
      continue;
    }

    // Blockquote
    if (line.startsWith(">")) {
      para = flushParagraph(para);
      const quoted = [];
      let buf = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        const content = lines[i].replace(/^>\s?/, "");
        if (content.trim() === "") {
          if (buf.length) quoted.push(buf.join(" "));
          buf = [];
        } else {
          buf.push(content);
        }
        i += 1;
      }
      if (buf.length) quoted.push(buf.join(" "));
      blocks.push({ type: "quote", paragraphs: quoted });
      continue;
    }

    // Lists — collect consecutive items, allowing wrapped continuation lines
    const bullet = /^(\s*)[-*]\s+(.*)$/.exec(line);
    const ordered = /^(\s*)(\d+)\.\s+(.*)$/.exec(line);
    if (bullet || ordered) {
      para = flushParagraph(para);
      const kind = bullet ? "ul" : "ol";
      const items = [];
      while (i < lines.length) {
        const b = /^(\s*)[-*]\s+(.*)$/.exec(lines[i]);
        const o = /^(\s*)(\d+)\.\s+(.*)$/.exec(lines[i]);
        const m = kind === "ul" ? b : o;
        if (m) {
          const indent = m[1].length;
          const text = kind === "ul" ? m[2] : m[3];
          items.push({ level: indent >= 2 ? 1 : 0, text: text.trim() });
          i += 1;
        } else if (
          items.length &&
          lines[i].trim() !== "" &&
          /^\s{2,}\S/.test(lines[i]) &&
          !b &&
          !o
        ) {
          // continuation of the previous item
          items[items.length - 1].text += ` ${lines[i].trim()}`;
          i += 1;
        } else {
          break;
        }
      }
      blocks.push({ type: kind, items });
      continue;
    }

    // Blank line ends a paragraph
    if (line.trim() === "") {
      para = flushParagraph(para);
      i += 1;
      continue;
    }

    para.push(line.trim());
    i += 1;
  }

  flushParagraph(para);
  return blocks;
}

/**
 * Parse a pipe table, honouring the alignment row.
 * @param {string[]} raw
 */
function parseTable(raw) {
  const split = (row) =>
    row
      .replace(/^\|/, "")
      .replace(/\|\s*$/, "")
      .split("|")
      .map((c) => c.trim());

  const header = split(raw[0]);
  let align = header.map(() => AlignmentType.LEFT);
  let bodyStart = 1;

  if (raw.length > 1 && /^[\s|:-]+$/.test(raw[1])) {
    align = split(raw[1]).map((spec) => {
      if (/^:-+:$/.test(spec)) return AlignmentType.CENTER;
      if (/-+:$/.test(spec)) return AlignmentType.RIGHT;
      return AlignmentType.LEFT;
    });
    bodyStart = 2;
  }

  const rows = raw.slice(bodyStart).map(split);
  return { type: "table", header, align, rows };
}

// ── Inline formatting ──────────────────────────────────────────────────

const INLINE_RE =
  /(`[^`]+`)|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+?\*\*)|(\*[^*]+?\*)/g;

/**
 * Convert inline Markdown to docx runs.
 * @param {string} text
 * @param {object} [opts]
 */
function inline(text, opts = {}) {
  const base = {
    font: opts.font || BODY_FONT,
    size: opts.size || SIZE_BODY,
    color: opts.color || INK,
    bold: opts.bold || false,
    italics: opts.italics || false,
  };
  const codeSize = Math.max(13, base.size - 3);
  const runs = [];
  let last = 0;
  let m;

  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) {
      runs.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    }
    const token = m[0];
    if (m[1]) {
      runs.push(
        new TextRun({
          ...base,
          text: token.slice(1, -1),
          font: MONO_FONT,
          size: codeSize,
          shading: { type: ShadingType.CLEAR, color: "auto", fill: INLINE_CODE_BG },
        }),
      );
    } else if (m[2]) {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      runs.push(
        new ExternalHyperlink({
          children: [new TextRun({ ...base, text: link[1], style: "Hyperlink" })],
          link: link[2],
        }),
      );
    } else if (m[3]) {
      runs.push(new TextRun({ ...base, text: token.slice(2, -2), bold: true }));
    } else {
      runs.push(new TextRun({ ...base, text: token.slice(1, -1), italics: true }));
    }
    last = m.index + token.length;
  }
  if (last < text.length) {
    runs.push(new TextRun({ ...base, text: text.slice(last) }));
  }
  return runs.length ? runs : [new TextRun({ ...base, text: "" })];
}

const stripEmphasis = (s) => s.replace(/^\*\*(.*)\*\*$/, "$1");

// ── Block renderers ────────────────────────────────────────────────────

function codeBlock(lines) {
  const border = {
    left: { style: BorderStyle.SINGLE, size: 12, color: CODE_BAR, space: 6 },
  };
  const body = lines.length ? lines : [""];
  return body.map((text, idx) => {
    // Word collapses leading whitespace in a run, so preserve indentation
    // with a non-breaking-space prefix.
    const leading = /^\s*/.exec(text)[0].length;
    const rendered = " ".repeat(leading) + text.slice(leading);
    return new Paragraph({
      shading: { type: ShadingType.CLEAR, color: "auto", fill: CODE_BG },
      border,
      indent: { left: 180 },
      spacing: {
        line: 240,
        before: idx === 0 ? 120 : 0,
        after: idx === body.length - 1 ? 180 : 0,
      },
      children: [
        new TextRun({
          text: rendered || " ",
          font: MONO_FONT,
          size: SIZE_CODE,
          color: "24282E",
        }),
      ],
    });
  });
}

function quoteBlock(paragraphs) {
  const body = paragraphs.length ? paragraphs : [""];
  return body.map((text, idx) => {
    return new Paragraph({
      shading: { type: ShadingType.CLEAR, color: "auto", fill: QUOTE_BG },
      border: {
        left: { style: BorderStyle.SINGLE, size: 12, color: QUOTE_BAR, space: 8 },
      },
      indent: { left: 220, right: 160 },
      spacing: {
        line: 276,
        before: idx === 0 ? 140 : 0,
        after: idx === body.length - 1 ? 180 : 80,
      },
      children: inline(text, { color: "3D3831" }),
    });
  });
}

function tableBlock(block) {
  const cols = block.header.length;

  // Size columns by their widest cell, with a floor so no column collapses.
  const weights = block.header.map((h, c) => {
    let widest = h.length;
    for (const row of block.rows) {
      widest = Math.max(widest, (row[c] || "").length);
    }
    return Math.max(widest, 6);
  });
  const total = weights.reduce((a, b) => a + b, 0);
  const columnWidths = weights.map((w) =>
    Math.max(760, Math.round((w / total) * CONTENT_WIDTH)),
  );
  // Correct rounding drift so the widths sum exactly to the content width.
  const drift = CONTENT_WIDTH - columnWidths.reduce((a, b) => a + b, 0);
  columnWidths[columnWidths.length - 1] += drift;

  const cell = (text, colIdx, isHeader, striped) =>
    new TableCell({
      width: { size: columnWidths[colIdx], type: WidthType.DXA },
      shading: isHeader
        ? { type: ShadingType.CLEAR, color: "auto", fill: TABLE_HEAD_BG }
        : striped
          ? { type: ShadingType.CLEAR, color: "auto", fill: "FAFBFC" }
          : undefined,
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      children: [
        new Paragraph({
          alignment: block.align[colIdx] || AlignmentType.LEFT,
          spacing: { line: 240, before: 0, after: 0 },
          children: inline(text, {
            font: isHeader ? HEAD_FONT : BODY_FONT,
            size: isHeader ? SIZE_TABLE_HEAD : SIZE_TABLE,
            bold: isHeader,
          }),
        }),
      ],
    });

  const rows = [
    new TableRow({
      tableHeader: true,
      children: block.header.map((h, c) => cell(h, c, true, false)),
    }),
    ...block.rows.map(
      (row, r) =>
        new TableRow({
          children: block.header.map((_, c) =>
            cell(row[c] || "", c, false, r % 2 === 1),
          ),
        }),
    ),
  ];

  const hair = { style: BorderStyle.SINGLE, size: 2, color: RULE };
  return new Table({
    columnWidths,
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "B9BEC6" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "B9BEC6" },
      left: hair,
      right: hair,
      insideHorizontal: hair,
      insideVertical: hair,
    },
    rows,
  });
}

function horizontalRule() {
  return new Paragraph({
    spacing: { before: 160, after: 200, line: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 1 } },
    children: [new TextRun({ text: "", size: 2 })],
  });
}

// ── Document assembly ──────────────────────────────────────────────────

function build(blocks) {
  const children = [];
  let listInstance = 0;

  // Title block: h1, then the bold subtitle, then the descriptor line.
  let cursor = 0;
  if (blocks[0] && blocks[0].type === "h1") {
    children.push(
      new Paragraph({
        spacing: { after: 130, line: 300 },
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 18, color: INK, space: 8 },
        },
        children: [
          new TextRun({
            text: blocks[0].text,
            font: HEAD_FONT,
            size: 46,
            bold: true,
            color: "0F1114",
          }),
        ],
      }),
    );
    cursor = 1;
    if (blocks[1] && blocks[1].type === "p") {
      children.push(
        new Paragraph({
          spacing: { before: 160, after: 110, line: 280 },
          children: [
            new TextRun({
              text: stripEmphasis(blocks[1].text),
              font: HEAD_FONT,
              size: 27,
              color: "2B3038",
            }),
          ],
        }),
      );
      cursor = 2;
    }
    if (blocks[2] && blocks[2].type === "p") {
      children.push(
        new Paragraph({
          spacing: { after: 300, line: 280 },
          children: inline(blocks[2].text, {
            font: HEAD_FONT,
            size: 20,
            color: INK_FAINT,
          }),
        }),
      );
      cursor = 3;
    }

    // Contents, then start the body on a fresh page.
    children.push(
      new Paragraph({
        spacing: { before: 240, after: 160 },
        children: [
          new TextRun({
            text: "Contents",
            font: HEAD_FONT,
            size: 28,
            bold: true,
            color: "0F1114",
          }),
        ],
      }),
      new TableOfContents("Contents", {
        hyperlink: true,
        headingStyleRange: "1-3",
      }),
      new Paragraph({ children: [new PageBreak()] }),
    );

    // Skip the leading rule that separates the title block from section 1.
    while (blocks[cursor] && blocks[cursor].type === "hr") cursor += 1;
  }

  for (let i = cursor; i < blocks.length; i += 1) {
    const block = blocks[i];
    switch (block.type) {
      case "h1":
      case "h2":
        children.push(
          new Paragraph({
            heading: HeadingLevel.HEADING_1,
            children: inline(block.text, {
              font: HEAD_FONT,
              size: 28,
              bold: true,
              color: "0F1114",
            }),
          }),
        );
        break;
      case "h3":
        children.push(
          new Paragraph({
            heading: HeadingLevel.HEADING_2,
            children: inline(block.text, {
              font: HEAD_FONT,
              size: 23,
              bold: true,
              color: "0F1114",
            }),
          }),
        );
        break;
      case "h4":
        children.push(
          new Paragraph({
            heading: HeadingLevel.HEADING_3,
            children: inline(block.text, {
              font: HEAD_FONT,
              size: 21,
              bold: true,
              color: "33373D",
            }),
          }),
        );
        break;
      case "p":
        children.push(
          new Paragraph({
            spacing: { after: 150, line: 276 },
            children: inline(block.text),
          }),
        );
        break;
      case "code":
        children.push(...codeBlock(block.lines));
        break;
      case "quote":
        children.push(...quoteBlock(block.paragraphs));
        break;
      case "ul":
      case "ol": {
        listInstance += 1;
        const reference = block.type === "ul" ? "wp-bullets" : "wp-numbers";
        for (const item of block.items) {
          children.push(
            new Paragraph({
              numbering: {
                reference,
                level: item.level,
                instance: listInstance,
              },
              spacing: { after: 90, line: 276 },
              children: inline(item.text),
            }),
          );
        }
        break;
      }
      case "table":
        children.push(tableBlock(block));
        // Tables need a trailing spacer or the next block hugs the border.
        children.push(
          new Paragraph({ spacing: { after: 0, line: 200 }, children: [] }),
        );
        break;
      case "hr":
        children.push(horizontalRule());
        break;
      default:
        break;
    }
  }

  return children;
}

function main() {
  if (!fs.existsSync(SOURCE)) {
    console.error(`error: ${SOURCE} not found`);
    process.exit(1);
  }

  let md = fs.readFileSync(SOURCE, "utf8");
  // Drop the trailing attribution; it belongs in the repo, not the document.
  md = md.replace(/\n---\n\n\*🤖 Generated with[\s\S]*$/, "\n");

  const blocks = parseBlocks(md);
  const children = build(blocks);

  const footer = new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 120, after: 0 },
        children: [
          new TextRun({
            text: `${RUNNING_TITLE}   ·   `,
            font: HEAD_FONT,
            size: 15,
            color: "B0B5BD",
          }),
          new TextRun({
            children: [PageNumber.CURRENT],
            font: HEAD_FONT,
            size: 16,
            color: "8A8F98",
          }),
        ],
      }),
    ],
  });

  const doc = new Document({
    creator: "SecureMCP",
    title: "A Layered Architecture for Governed MCP",
    description: "The SecureMCP Design",
    // Without this the table of contents renders empty until the reader
    // manually refreshes the field.
    features: { updateFields: true },
    styles: {
      default: {
        document: {
          run: { font: BODY_FONT, size: SIZE_BODY, color: INK },
          paragraph: { spacing: { line: 276, after: 150 } },
        },
        heading1: {
          run: { font: HEAD_FONT, size: 28, bold: true, color: "0F1114" },
          paragraph: {
            spacing: { before: 400, after: 140, line: 260 },
            keepNext: true,
            border: {
              bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 4 },
            },
          },
        },
        heading2: {
          run: { font: HEAD_FONT, size: 23, bold: true, color: "0F1114" },
          paragraph: {
            spacing: { before: 280, after: 100, line: 260 },
            keepNext: true,
          },
        },
        heading3: {
          run: { font: HEAD_FONT, size: 21, bold: true, color: "33373D" },
          paragraph: {
            spacing: { before: 220, after: 80, line: 260 },
            keepNext: true,
          },
        },
      },
      paragraphStyles: [
        {
          id: "Hyperlink",
          name: "Hyperlink",
          basedOn: "Normal",
          run: { color: INK_SOFT, underline: {} },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "wp-bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "•",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 440, hanging: 250 } } },
            },
            {
              level: 1,
              format: LevelFormat.BULLET,
              text: "◦",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 880, hanging: 250 } } },
            },
          ],
        },
        {
          reference: "wp-numbers",
          levels: [
            {
              level: 0,
              format: LevelFormat.DECIMAL,
              text: "%1.",
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: 470, hanging: 280 } } },
            },
            {
              level: 1,
              format: LevelFormat.LOWER_LETTER,
              text: "%2.",
              alignment: AlignmentType.START,
              style: { paragraph: { indent: { left: 940, hanging: 280 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          titlePage: true,
          page: {
            size: { width: PAGE_WIDTH, height: 15840 },
            margin: {
              top: 1440,
              bottom: 1300,
              left: MARGIN_X,
              right: MARGIN_X,
              footer: 620,
            },
          },
        },
        footers: { default: footer, first: new Footer({ children: [] }) },
        children,
      },
    ],
  });

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  Packer.toBuffer(doc).then((buf) => {
    fs.writeFileSync(OUT, buf);
    const kb = (buf.length / 1024).toFixed(0);
    console.log(`wrote ${path.relative(ROOT, OUT)} (${kb} KB)`);
    console.log(
      `${blocks.length} blocks · ${children.length} body elements · ` +
        `${blocks.filter((b) => b.type === "table").length} tables · ` +
        `${blocks.filter((b) => b.type === "code").length} code blocks`,
    );
  });
}

main();

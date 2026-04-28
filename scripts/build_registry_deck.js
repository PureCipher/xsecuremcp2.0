// Builds the Secure MCP Registry deck (semi-technical audience).
// Run with: node scripts/build_registry_deck.js
//
// Layered narrative: MCP → FastMCP → SecureMCP → Registry → Clients
// → Activity & Simulator → Onboarding → Takeaways. 10 slides.

const pptxgen = require("pptxgenjs");

// ── Palette ──────────────────────────────────────────────────
// Inspired by the registry UI's actual accents (deep blue + teal)
// against a warm cream content surface.
const NAVY      = "0F2747"; // dominant — title slides, callouts
const STEEL     = "1E5FA4"; // primary accent
const TEAL      = "0F8B8D"; // secondary accent
const AMBER     = "C0792E"; // sparingly, for emphasis
const CREAM     = "F4F1EA"; // content slide bg
const SURFACE   = "FFFFFF"; // card bg
const INK       = "0F1419"; // strongest text
const INK_SOFT  = "33415C"; // body text
const INK_MUTED = "5F6B7C"; // captions
const RULE      = "D6D2C8"; // hairlines on cream
const RULE_SOFT = "EAE6DC";

const FONT_HEAD = "Calibri";
const FONT_BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" × 7.5" — gives the feature grids room
pres.author = "PureCipher";
pres.title  = "Secure MCP Registry — from MCP to a governed runtime";

const W = 13.3;
const H = 7.5;

// ── Reusable chrome ─────────────────────────────────────────
function brandStrip(slide, opts = {}) {
  const dark = opts.dark === true;
  // Top hairline + tiny brand chip top-left.
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 0.06,
    fill: { color: dark ? STEEL : NAVY }, line: { color: dark ? STEEL : NAVY },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: W - 1.5, y: 0, w: 1.5, h: 0.06,
    fill: { color: TEAL }, line: { color: TEAL },
  });
  slide.addText("PURECIPHER · SECURE MCP REGISTRY", {
    x: 0.55, y: 0.18, w: 6, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 9.5, bold: true,
    charSpacing: 4, color: dark ? "BFD3E8" : INK_MUTED, margin: 0,
  });
  // Page numbering — set from caller
}

function pageNumber(slide, n) {
  slide.addText(`${n} / 10`, {
    x: W - 0.95, y: H - 0.4, w: 0.6, h: 0.25,
    fontFace: FONT_HEAD, fontSize: 9, color: INK_MUTED, align: "right", margin: 0,
  });
}

function sectionTitle(slide, eyebrow, title, subtitle) {
  slide.addText(eyebrow, {
    x: 0.55, y: 0.55, w: 9, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 4,
    color: TEAL, margin: 0,
  });
  slide.addText(title, {
    x: 0.55, y: 0.88, w: 12.2, h: 0.85,
    fontFace: FONT_HEAD, fontSize: 30, bold: true, color: INK,
    margin: 0,
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 0.55, y: 1.72, w: 11.5, h: 0.5,
      fontFace: FONT_BODY, fontSize: 14, color: INK_SOFT, margin: 0,
    });
  }
}

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: opts.fill || SURFACE },
    line: { color: opts.border || RULE, width: 0.75 },
  });
  if (opts.accent) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.05, h,
      fill: { color: opts.accent }, line: { color: opts.accent },
    });
  }
}

function tinyBadge(slide, x, y, w, label, fill, fg) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 0.28,
    fill: { color: fill }, line: { color: fill },
  });
  slide.addText(label, {
    x, y, w, h: 0.28,
    fontFace: FONT_HEAD, fontSize: 9, bold: true, charSpacing: 3,
    color: fg, align: "center", valign: "middle", margin: 0,
  });
}

function numberedDot(slide, x, y, n, color = TEAL) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: 0.42, h: 0.42,
    fill: { color }, line: { color },
  });
  slide.addText(String(n), {
    x, y, w: 0.42, h: 0.42,
    fontFace: FONT_HEAD, fontSize: 14, bold: true,
    color: "FFFFFF", align: "center", valign: "middle", margin: 0,
  });
}

// ── Slide 1: Title ───────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  // Decorative diagonal accent block
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.18, h: H,
    fill: { color: TEAL }, line: { color: TEAL },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.18, y: 0, w: 0.06, h: H,
    fill: { color: STEEL }, line: { color: STEEL },
  });

  s.addText("PURECIPHER", {
    x: 0.9, y: 0.85, w: 6, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, charSpacing: 5,
    color: "8FB3DA", margin: 0,
  });

  s.addText("Secure MCP Registry", {
    x: 0.9, y: 1.45, w: 11, h: 1.2,
    fontFace: FONT_HEAD, fontSize: 56, bold: true, color: "FFFFFF", margin: 0,
  });

  s.addText("From MCP, up to a governed runtime.", {
    x: 0.9, y: 2.85, w: 11, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 28, color: "CADCFC", margin: 0,
  });

  // Layered stack visual on the right
  const stackLeft = 7.6;
  const layers = [
    { label: "Registry  (catalog · publishers · listings)", c: STEEL  },
    { label: "SecureMCP  (policy · contracts · consent · provenance · reflexive)", c: "1A4A8C" },
    { label: "FastMCP  (Python framework · transports · SDK)", c: "133766" },
    { label: "MCP  (open protocol · tools · resources · prompts)", c: "0C2A4E" },
  ];
  let ly = 4.2;
  for (const layer of layers) {
    s.addShape(pres.shapes.RECTANGLE, {
      x: stackLeft, y: ly, w: 5.0, h: 0.55,
      fill: { color: layer.c }, line: { color: "FFFFFF", width: 0.5 },
    });
    s.addText(layer.label, {
      x: stackLeft + 0.18, y: ly, w: 4.7, h: 0.55,
      fontFace: FONT_HEAD, fontSize: 11, bold: true, color: "FFFFFF",
      valign: "middle", margin: 0,
    });
    ly += 0.55;
  }
  s.addText("each layer adds trust → builds on the one below", {
    x: stackLeft, y: ly + 0.05, w: 5.0, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, italic: true,
    color: "8FB3DA", align: "right", margin: 0,
  });

  // Bottom byline
  s.addText("A semi-technical walkthrough", {
    x: 0.9, y: H - 0.95, w: 6, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, charSpacing: 3,
    color: TEAL, margin: 0,
  });
  s.addText("Identity · policy · provenance · live behaviour — for every MCP call your agents make.", {
    x: 0.9, y: H - 0.6, w: 11, h: 0.4,
    fontFace: FONT_BODY, fontSize: 13, color: "8FB3DA", margin: 0,
  });
}

// ── Slide 2: What is MCP? ────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 2);

  sectionTitle(
    s,
    "LAYER 1",
    "MCP — Model Context Protocol",
    "An open standard for plugging tools, data, and prompts into any LLM client.",
  );

  // Left: narrative paragraph
  s.addText([
    { text: "MCP is the wire protocol. ", options: { bold: true, color: INK } },
    { text: "It defines how an LLM-driven client (Claude Desktop, Cursor, an agent runtime) discovers what an external server can do, and how it calls those capabilities — using JSON-RPC over stdio or HTTP.", options: { color: INK_SOFT } },
  ], {
    x: 0.55, y: 2.55, w: 6.0, h: 1.6,
    fontFace: FONT_BODY, fontSize: 14, margin: 0, paraSpaceAfter: 4,
  });
  s.addText([
    { text: "It standardises three things a server can offer:", options: { color: INK_SOFT } },
  ], {
    x: 0.55, y: 4.1, w: 6.0, h: 0.4,
    fontFace: FONT_BODY, fontSize: 13, margin: 0,
  });
  s.addText([
    { text: "Tools  ",  options: { bold: true, color: INK } },
    { text: "— callable functions (search, send_email, run_query)", options: { color: INK_SOFT, breakLine: true } },
    { text: "Resources  ", options: { bold: true, color: INK } },
    { text: "— addressable data (file://…, db://…, https://…)", options: { color: INK_SOFT, breakLine: true } },
    { text: "Prompts  ", options: { bold: true, color: INK } },
    { text: "— pre-authored interaction templates", options: { color: INK_SOFT } },
  ], {
    x: 0.55, y: 4.55, w: 6.0, h: 1.7,
    fontFace: FONT_BODY, fontSize: 13, margin: 0, paraSpaceAfter: 4,
  });

  // Right: client → server diagram card
  const cx = 7.0, cy = 2.5, cw = 5.8, ch = 4.4;
  card(s, cx, cy, cw, ch, { accent: TEAL });

  s.addText("How a call flows", {
    x: cx + 0.3, y: cy + 0.18, w: cw - 0.4, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });

  // Client box (narrower, leaves room for arrow labels in the middle)
  const clientW = 1.7, serverW = 1.7;
  const clientX = cx + 0.3;
  const serverX = cx + cw - 0.3 - serverW;
  s.addShape(pres.shapes.RECTANGLE, {
    x: clientX, y: cy + 0.7, w: clientW, h: 0.85,
    fill: { color: "EAF1FA" }, line: { color: STEEL, width: 1 },
  });
  s.addText([
    { text: "MCP Client",     options: { bold: true, color: NAVY, breakLine: true } },
    { text: "agent · IDE · desktop", options: { color: INK_SOFT } },
  ], {
    x: clientX, y: cy + 0.7, w: clientW, h: 0.85,
    fontFace: FONT_BODY, fontSize: 10.5, align: "center", valign: "middle", margin: 0,
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: serverX, y: cy + 0.7, w: serverW, h: 0.85,
    fill: { color: "E5F1F1" }, line: { color: TEAL, width: 1 },
  });
  s.addText([
    { text: "MCP Server",   options: { bold: true, color: TEAL, breakLine: true } },
    { text: "tools · resources · prompts", options: { color: INK_SOFT } },
  ], {
    x: serverX, y: cy + 0.7, w: serverW, h: 0.85,
    fontFace: FONT_BODY, fontSize: 10.5, align: "center", valign: "middle", margin: 0,
  });

  // Arrows between (labels sit clearly above/below each line)
  const arrowX = clientX + clientW;
  const arrowW = serverX - arrowX;
  s.addText("list_tools / call_tool", {
    x: arrowX, y: cy + 0.72, w: arrowW, h: 0.22,
    fontFace: FONT_BODY, fontSize: 10, color: NAVY, align: "center", italic: true, margin: 0,
  });
  s.addShape(pres.shapes.LINE, {
    x: arrowX, y: cy + 1.0, w: arrowW, h: 0,
    line: { color: NAVY, width: 1.5, endArrowType: "triangle" },
  });
  s.addShape(pres.shapes.LINE, {
    x: arrowX, y: cy + 1.32, w: arrowW, h: 0,
    line: { color: TEAL, width: 1.5, beginArrowType: "triangle" },
  });
  s.addText("result · resource · stream", {
    x: arrowX, y: cy + 1.4, w: arrowW, h: 0.22,
    fontFace: FONT_BODY, fontSize: 10, color: TEAL, align: "center", italic: true, margin: 0,
  });

  // Transports row
  s.addText("Transports", {
    x: cx + 0.4, y: cy + 1.95, w: cw - 0.8, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  const transports = ["stdio", "HTTP", "SSE", "streamable-http"];
  let tx = cx + 0.4;
  for (const t of transports) {
    s.addShape(pres.shapes.RECTANGLE, {
      x: tx, y: cy + 2.3, w: 1.25, h: 0.4,
      fill: { color: SURFACE }, line: { color: RULE, width: 0.75 },
    });
    s.addText(t, {
      x: tx, y: cy + 2.3, w: 1.25, h: 0.4,
      fontFace: FONT_BODY, fontSize: 10, color: INK,
      align: "center", valign: "middle", margin: 0,
    });
    tx += 1.32;
  }

  // Footnote
  s.addText("Open standard. Vendor-neutral. Anyone can write a client or a server.", {
    x: cx + 0.4, y: cy + ch - 0.95, w: cw - 0.8, h: 0.6,
    fontFace: FONT_BODY, fontSize: 11, italic: true, color: INK_SOFT, margin: 0,
  });
  s.addText("Think: the USB-C of the LLM tool ecosystem.", {
    x: cx + 0.4, y: cy + ch - 0.45, w: cw - 0.8, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, bold: true, color: NAVY, margin: 0,
  });
}

// ── Slide 3: What is FastMCP? ────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 3);

  sectionTitle(
    s,
    "LAYER 2",
    "FastMCP — the Python framework that ate MCP",
    "Decorators, typed parameters, multi-transport, a real client SDK. It is how most production MCP servers are written.",
  );

  // Left card — code-style "feel"
  const codeX = 0.55, codeY = 2.5, codeW = 6.4, codeH = 4.3;
  card(s, codeX, codeY, codeW, codeH, { fill: "0F1F38" });
  s.addText("server.py", {
    x: codeX + 0.3, y: codeY + 0.18, w: codeW - 0.6, h: 0.3,
    fontFace: "Courier New", fontSize: 10, color: "8FB3DA", margin: 0,
  });
  s.addShape(pres.shapes.LINE, {
    x: codeX + 0.3, y: codeY + 0.5, w: codeW - 0.6, h: 0,
    line: { color: "1F3A66", width: 0.5 },
  });
  const codeLines = [
    { text: "from fastmcp import FastMCP", c: "8FB3DA" },
    { text: "",                            c: "8FB3DA" },
    { text: "mcp = FastMCP(\"acme-tools\")", c: "FFFFFF" },
    { text: "",                            c: "FFFFFF" },
    { text: "@mcp.tool",                   c: "F0B86E" },
    { text: "def search(query: str) -> list[str]:", c: "FFFFFF" },
    { text: "    \"\"\"Free-text search across the catalog.\"\"\"", c: "8AA8C2" },
    { text: "    return engine.query(query)", c: "FFFFFF" },
    { text: "",                            c: "FFFFFF" },
    { text: "@mcp.resource(\"catalog://{slug}\")", c: "F0B86E" },
    { text: "def catalog(slug: str) -> dict: ...",  c: "FFFFFF" },
    { text: "",                            c: "FFFFFF" },
    { text: "mcp.run(transport=\"streamable-http\")", c: "7AC5C9" },
  ];
  let cy = codeY + 0.65;
  for (const ln of codeLines) {
    s.addText(ln.text || " ", {
      x: codeX + 0.4, y: cy, w: codeW - 0.6, h: 0.26,
      fontFace: "Courier New", fontSize: 12, color: ln.c, margin: 0,
    });
    cy += 0.26;
  }

  // Right side — what FastMCP gives you
  const rx = 7.4, ry = 2.5, rw = 5.4;
  s.addText("What FastMCP adds on top of MCP", {
    x: rx, y: ry, w: rw, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });

  const feats = [
    { num: "1", title: "Decorator surface",        body: "@tool, @resource, @prompt — Python type hints become the wire schema. No JSON-Schema by hand." },
    { num: "2", title: "All transports built-in", body: "stdio, HTTP, SSE, streamable-http — flip via one argument; pick what your client speaks." },
    { num: "3", title: "Client SDK",               body: "Programmatic Client class for testing and orchestration: list_tools(), call_tool(), session lifecycle." },
    { num: "4", title: "Middleware chain",         body: "Pluggable hooks around every request — the seam SecureMCP plugs into next." },
  ];
  let fy = ry + 0.5;
  for (const f of feats) {
    numberedDot(s, rx, fy, f.num, STEEL);
    s.addText(f.title, {
      x: rx + 0.6, y: fy - 0.02, w: rw - 0.6, h: 0.32,
      fontFace: FONT_HEAD, fontSize: 13, bold: true, color: INK, margin: 0,
    });
    s.addText(f.body, {
      x: rx + 0.6, y: fy + 0.3, w: rw - 0.6, h: 0.7,
      fontFace: FONT_BODY, fontSize: 11.5, color: INK_SOFT, margin: 0,
    });
    fy += 1.05;
  }
}

// ── Slide 4: What is SecureMCP? ──────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 4);

  sectionTitle(
    s,
    "LAYER 3",
    "SecureMCP — the governance shell around any MCP server",
    "Five pluggable middleware planes that wrap a FastMCP server. Each one watches a different aspect of every call. Opt-in, observable, hot-toggleable.",
  );

  // Center: a wrapping diagram — concentric: server → planes → client
  const cx = 6.65, cy = 4.7;
  // Outer ring
  s.addShape(pres.shapes.OVAL, {
    x: cx - 3.3, y: cy - 1.65, w: 6.6, h: 3.3,
    fill: { color: "E9F1F1" }, line: { color: TEAL, width: 1.5, dashType: "dash" },
  });
  // Inner: server
  s.addShape(pres.shapes.OVAL, {
    x: cx - 1.0, y: cy - 0.55, w: 2.0, h: 1.1,
    fill: { color: NAVY }, line: { color: NAVY },
  });
  s.addText([
    { text: "FastMCP server", options: { bold: true, breakLine: true, color: "FFFFFF" } },
    { text: "your tools",     options: { color: "BFD3E8" } },
  ], {
    x: cx - 1.0, y: cy - 0.55, w: 2.0, h: 1.1,
    fontFace: FONT_BODY, fontSize: 11, align: "center", valign: "middle", margin: 0,
  });

  // Plane chips around the ring — symmetric placement, clearly
  // OUTSIDE the dashed ellipse, with the bottom chips on the
  // left/right rather than dead-bottom (the bottom-center slot
  // collides with the caption zone underneath the diagram).
  const planes = [
    { x: cx - 4.0,  y: cy - 2.35, label: "Policy",     c: STEEL },
    { x: cx - 0.85, y: cy - 2.55, label: "Contracts",  c: TEAL  },
    { x: cx + 2.3,  y: cy - 2.35, label: "Consent",    c: AMBER },
    { x: cx + 2.3,  y: cy + 1.55, label: "Provenance", c: STEEL },
    { x: cx - 4.0,  y: cy + 1.55, label: "Reflexive",  c: TEAL  },
  ];
  for (const p of planes) {
    s.addShape(pres.shapes.RECTANGLE, {
      x: p.x, y: p.y, w: 1.7, h: 0.5,
      fill: { color: p.c }, line: { color: p.c },
    });
    s.addText(p.label, {
      x: p.x, y: p.y, w: 1.7, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "FFFFFF",
      align: "center", valign: "middle", margin: 0,
    });
  }

  // Caller chip on the far left
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55, y: cy - 0.3, w: 1.6, h: 0.6,
    fill: { color: SURFACE }, line: { color: NAVY, width: 1 },
  });
  s.addText("client call", {
    x: 0.55, y: cy - 0.3, w: 1.6, h: 0.6,
    fontFace: FONT_BODY, fontSize: 11, color: NAVY,
    align: "center", valign: "middle", margin: 0,
  });
  s.addShape(pres.shapes.LINE, {
    x: 2.15, y: cy, w: 1.15, h: 0,
    line: { color: NAVY, width: 1.5, endArrowType: "triangle" },
  });

  // Caption under diagram
  s.addText(
    "Every request walks the chain. Any plane can deny, attach a contract clause, " +
    "or write a record. None of them require the underlying server to know they exist.",
    {
      x: 1.6, y: 6.6, w: 10.1, h: 0.7,
      fontFace: FONT_BODY, fontSize: 13, italic: true, color: INK_SOFT,
      align: "center", margin: 0,
    },
  );
}

// ── Slide 5: The five control planes ────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 5);

  sectionTitle(
    s,
    "INSIDE LAYER 3",
    "The five control planes",
    "What each plane gates, and what each plane records — keyed by the caller's identity.",
  );

  const startY = 2.45;
  const rowH = 0.72;
  const cardH = 0.7 + rowH * 5 + 0.15; // header + 5 rows + bottom padding
  // header
  card(s, 0.55, startY, 12.2, cardH, { fill: SURFACE });

  // Header row
  const cols = [
    { x: 0.75, w: 2.1, label: "PLANE" },
    { x: 2.95, w: 4.5, label: "WHAT IT DOES" },
    { x: 7.5,  w: 5.1, label: "EVIDENCE IT LEAVES BEHIND" },
  ];
  let hy = startY + 0.18;
  for (const c of cols) {
    s.addText(c.label, {
      x: c.x, y: hy, w: c.w, h: 0.32,
      fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 3,
      color: INK_MUTED, margin: 0,
    });
  }
  // separator
  s.addShape(pres.shapes.LINE, {
    x: 0.75, y: startY + 0.55, w: 11.85, h: 0,
    line: { color: RULE, width: 0.75 },
  });

  const rows = [
    {
      plane: "Policy Kernel",
      color: STEEL,
      gate:  "Allow / deny / defer per request, evaluated against pluggable providers (RBAC, ABAC, allowlist, rate-limit, temporal, compliance).",
      log:   "PolicyResult — decision, reason, policy_id, constraints. Optional audit row.",
    },
    {
      plane: "Contract Broker",
      color: TEAL,
      gate:  "Negotiates and validates agent ↔ server contracts: which actions, which terms, what duration.",
      log:   "Contract record — agent_id, server_id, term list, status, signatures.",
    },
    {
      plane: "Consent Graph",
      color: AMBER,
      gate:  "Source → target → scope checks across delegation chains (read / write / execute, with expiry).",
      log:   "ConsentDecision — granted, the path of edges that authorised it.",
    },
    {
      plane: "Provenance Ledger",
      color: STEEL,
      gate:  "Append-only, hash-linked record of every call. Tamper-evident chain.",
      log:   "ProvenanceRecord — actor_id, action, resource, input/output hashes, prev_hash.",
    },
    {
      plane: "Reflexive Core",
      color: TEAL,
      gate:  "Learns each actor's behavioural baseline; flags drift in real time.",
      log:   "DriftEvent — metric, sigma deviation, severity (info → critical).",
    },
  ];

  let ry = startY + 0.7;
  for (const r of rows) {
    // accent bar
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.75, y: ry, w: 0.06, h: rowH - 0.15,
      fill: { color: r.color }, line: { color: r.color },
    });
    s.addText(r.plane, {
      x: 0.95, y: ry, w: 1.95, h: rowH,
      fontFace: FONT_HEAD, fontSize: 12, bold: true, color: INK, margin: 0,
      valign: "middle",
    });
    s.addText(r.gate, {
      x: 2.95, y: ry, w: 4.5, h: rowH,
      fontFace: FONT_BODY, fontSize: 10.5, color: INK_SOFT, margin: 0,
      valign: "middle",
    });
    s.addText(r.log, {
      x: 7.5, y: ry, w: 5.1, h: rowH,
      fontFace: FONT_BODY, fontSize: 10.5, color: INK_SOFT, italic: true, margin: 0,
      valign: "middle",
    });
    ry += rowH;
    s.addShape(pres.shapes.LINE, {
      x: 0.75, y: ry - 0.05, w: 11.85, h: 0,
      line: { color: RULE_SOFT, width: 0.5 },
    });
  }

  s.addText(
    "Each plane is opt-in, hot-toggleable from the admin UI, and individually testable.",
    {
      x: 0.55, y: H - 0.7, w: 12, h: 0.32,
      fontFace: FONT_BODY, fontSize: 12, italic: true, color: INK_MUTED,
      align: "center", margin: 0,
    },
  );
}

// ── Slide 6: PureCipher Registry ─────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 6);

  sectionTitle(
    s,
    "LAYER 4",
    "The Registry — a vetted catalog of MCP tools",
    "Built on top of SecureMCP. Every listing is signed, the upstream is pinned, and the trust posture is visible before anyone calls it.",
  );

  // Left: anatomy of a listing
  const lx = 0.55, ly = 2.5, lw = 6.0, lh = 4.4;
  card(s, lx, ly, lw, lh, { accent: STEEL });
  s.addText("Anatomy of a listing", {
    x: lx + 0.3, y: ly + 0.2, w: lw - 0.4, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });

  const items = [
    { k: "Identity",     v: "tool_name · version · publisher_id · author" },
    { k: "Manifest",     v: "declared permissions, data flows, classifications" },
    { k: "Attestation",  v: "AUTHOR (publisher self-signs) or CURATOR (a vouching reviewer)" },
    { k: "Upstream",     v: "channel + identifier + pinned hash · npm, PyPI, Docker, HTTP" },
    { k: "Certification", v: "level set by the certification pipeline" },
    { k: "Status",       v: "DRAFT → PENDING_REVIEW → PUBLISHED → SUSPENDED" },
  ];
  let iy = ly + 0.65;
  for (const it of items) {
    s.addText(it.k, {
      x: lx + 0.3, y: iy, w: 1.55, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 2,
      color: TEAL, margin: 0,
    });
    s.addText(it.v, {
      x: lx + 1.9, y: iy, w: lw - 2.1, h: 0.5,
      fontFace: FONT_BODY, fontSize: 11.5, color: INK_SOFT, margin: 0,
    });
    iy += 0.6;
  }

  // Right: hosting modes + attestation kinds
  const rx = 6.85, ry = 2.5, rw = 5.9;

  // Hosting modes card
  const hmH = 2.5;
  card(s, rx, ry, rw, hmH, { accent: TEAL });
  s.addText("Hosting modes", {
    x: rx + 0.3, y: ry + 0.18, w: rw - 0.4, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  const modes = [
    { l: "CATALOG",  v: "linkable spec — clients run it themselves" },
    { l: "PROXY",    v: "registry-hosted gateway · enforces allowlist" },
  ];
  let my = ry + 0.62;
  for (const m of modes) {
    tinyBadge(s, rx + 0.3, my, 0.95, m.l, NAVY, "FFFFFF");
    s.addText(m.v, {
      x: rx + 1.4, y: my - 0.03, w: rw - 1.6, h: 0.35,
      fontFace: FONT_BODY, fontSize: 11.5, color: INK_SOFT, margin: 0, valign: "middle",
    });
    my += 0.46;
  }
  // channel chips — anchored a clear gap below the modes block
  const chips = ["http", "pypi", "npm", "docker"];
  s.addText("Supported upstream channels", {
    x: rx + 0.3, y: my + 0.12, w: rw - 0.4, h: 0.25,
    fontFace: FONT_HEAD, fontSize: 9.5, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  let chx = rx + 0.3;
  const chy = my + 0.45;
  for (const c of chips) {
    s.addShape(pres.shapes.RECTANGLE, {
      x: chx, y: chy, w: 1.0, h: 0.36,
      fill: { color: "EDF1F0" }, line: { color: TEAL, width: 0.5 },
    });
    s.addText(c, {
      x: chx, y: chy, w: 1.0, h: 0.36,
      fontFace: "Courier New", fontSize: 11, color: TEAL,
      align: "center", valign: "middle", margin: 0,
    });
    chx += 1.06;
  }

  // Attestation kinds
  const akY = ry + hmH + 0.2;
  const akH = 1.7;
  card(s, rx, akY, rw, akH, { accent: AMBER });
  s.addText("Attestation kinds", {
    x: rx + 0.3, y: akY + 0.18, w: rw - 0.4, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  s.addText([
    { text: "AUTHOR  ", options: { bold: true, color: STEEL } },
    { text: "— the publisher signs their own listing.", options: { color: INK_SOFT, breakLine: true } },
    { text: "CURATOR  ", options: { bold: true, color: AMBER } },
    { text: "— a registry curator vouches for an upstream MCP server they observed (e.g. a popular npm server). The original author isn't involved.", options: { color: INK_SOFT } },
  ], {
    x: rx + 0.3, y: akY + 0.6, w: rw - 0.6, h: akH - 0.7,
    fontFace: FONT_BODY, fontSize: 11.5, margin: 0, paraSpaceAfter: 4,
  });
}

// ── Slide 7: Onboarding flow ─────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 7);

  sectionTitle(
    s,
    "WORKFLOW",
    "How a tool becomes a published listing",
    "Two onboarding paths feed the same review queue. Humans approve. Nothing reaches the catalog without an audit trail.",
  );

  // Two-column path comparison
  const top = 2.45;
  const colH = 3.85;

  // Path A: Publisher
  card(s, 0.55, top, 6.05, colH, { accent: STEEL });
  s.addText("PATH A · PUBLISHER", {
    x: 0.75, y: top + 0.18, w: 5.7, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 4,
    color: STEEL, margin: 0,
  });
  s.addText("The author signs their own listing", {
    x: 0.75, y: top + 0.5, w: 5.7, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: INK, margin: 0,
  });
  const stepsA = [
    "init   — scaffold a project with a security-manifest template",
    "check  — sync artifacts, verify the manifest, run preflight",
    "package — write the publish-ready dist artifacts",
    "publish — upload, sign, receive PENDING_REVIEW",
  ];
  let ay = top + 1.05;
  let stepN = 1;
  for (const st of stepsA) {
    numberedDot(s, 0.75, ay - 0.02, stepN, STEEL);
    s.addText(st, {
      x: 1.35, y: ay - 0.02, w: 5.1, h: 0.42,
      fontFace: "Courier New", fontSize: 11, color: INK_SOFT,
      valign: "middle", margin: 0,
    });
    ay += 0.55; stepN += 1;
  }
  s.addText(
    "Captured on publish: manifest · attestation · package digest · publisher identity.",
    {
      x: 0.75, y: top + colH - 0.85, w: 5.7, h: 0.6,
      fontFace: FONT_BODY, fontSize: 11, italic: true, color: INK_MUTED, margin: 0,
    },
  );

  // Path B: Curator
  card(s, 6.7, top, 6.05, colH, { accent: AMBER });
  s.addText("PATH B · CURATOR", {
    x: 6.9, y: top + 0.18, w: 5.7, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 11, bold: true, charSpacing: 4,
    color: AMBER, margin: 0,
  });
  s.addText("A reviewer vouches for an upstream", {
    x: 6.9, y: top + 0.5, w: 5.7, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: INK, margin: 0,
  });
  const stepsB = [
    "resolve   — paste an npm / pypi / docker / http upstream",
    "introspect — registry connects, lists tools, derives a draft manifest",
    "submit    — curator confirms scope, signs, lands as PENDING_REVIEW",
    "review    — moderator approves, rejects, or asks for changes",
  ];
  ay = top + 1.05; stepN = 1;
  for (const st of stepsB) {
    numberedDot(s, 6.9, ay - 0.02, stepN, AMBER);
    s.addText(st, {
      x: 7.5, y: ay - 0.02, w: 5.1, h: 0.42,
      fontFace: "Courier New", fontSize: 11, color: INK_SOFT,
      valign: "middle", margin: 0,
    });
    ay += 0.55; stepN += 1;
  }
  s.addText(
    "The original tool author isn't involved. The curator's identity is what's vouched.",
    {
      x: 6.9, y: top + colH - 0.85, w: 5.7, h: 0.6,
      fontFace: FONT_BODY, fontSize: 11, italic: true, color: INK_MUTED, margin: 0,
    },
  );

  // Bottom funnel
  const fy = top + colH + 0.25;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 1.2, y: fy, w: 10.9, h: 0.5,
    fill: { color: NAVY }, line: { color: NAVY },
  });
  s.addText(
    "→ both paths land in the same Review Queue (Reviewer / Admin) → PUBLISHED",
    {
      x: 1.2, y: fy, w: 10.9, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 13, bold: true, color: "FFFFFF",
      align: "center", valign: "middle", margin: 0,
    },
  );
}

// ── Slide 8: MCP Clients & identity ──────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 8);

  sectionTitle(
    s,
    "LAYER 5",
    "MCP Clients — finally, real identities",
    "Until recently, every plane saw a different opaque token prefix. Now every authenticated request flows through with one stable slug.",
  );

  // Left: the problem and the fix (narrative)
  const lx = 0.55, ly = 2.5, lw = 6.1, lh = 4.4;
  card(s, lx, ly, lw, lh, { fill: SURFACE });
  s.addText("BEFORE", {
    x: lx + 0.3, y: ly + 0.2, w: lw - 0.6, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 4,
    color: AMBER, margin: 0,
  });
  s.addText([
    { text: "Each plane independently extracted ", options: { color: INK_SOFT } },
    { text: "actor_id", options: { fontFace: "Courier New", color: INK } },
    { text: " from the bearer token's first 8 chars (", options: { color: INK_SOFT } },
    { text: "\"pcc_abc1…\"", options: { fontFace: "Courier New", color: AMBER } },
    { text: "). Telemetry never agreed across planes — you couldn't ask: ‘what has Claude Desktop done in the last hour?'", options: { color: INK_SOFT } },
  ], {
    x: lx + 0.3, y: ly + 0.55, w: lw - 0.6, h: 1.4,
    fontFace: FONT_BODY, fontSize: 12, margin: 0,
  });

  // Hairline
  s.addShape(pres.shapes.LINE, {
    x: lx + 0.3, y: ly + 2.05, w: lw - 0.6, h: 0,
    line: { color: RULE, width: 0.75 },
  });
  s.addText("AFTER", {
    x: lx + 0.3, y: ly + 2.2, w: lw - 0.6, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 4,
    color: TEAL, margin: 0,
  });
  s.addText([
    { text: "A registered ", options: { color: INK_SOFT } },
    { text: "RegistryClient", options: { fontFace: "Courier New", color: INK } },
    { text: " has a stable ", options: { color: INK_SOFT } },
    { text: "slug", options: { fontFace: "Courier New", color: INK } },
    { text: " (", options: { color: INK_SOFT } },
    { text: "claude-desktop", options: { fontFace: "Courier New", color: TEAL } },
    { text: ", ", options: { color: INK_SOFT } },
    { text: "acme-ci-bot", options: { fontFace: "Courier New", color: TEAL } },
    { text: "). A resolver middleware reads the bearer token and writes the slug into a ContextVar. Every downstream plane uses it as ", options: { color: INK_SOFT } },
    { text: "actor_id", options: { fontFace: "Courier New", color: INK } },
    { text: ". Same identity, every plane.", options: { color: INK_SOFT } },
  ], {
    x: lx + 0.3, y: ly + 2.55, w: lw - 0.6, h: 1.7,
    fontFace: FONT_BODY, fontSize: 12, margin: 0,
  });

  // Right: identity card mock
  const cx = 6.85, cy = 2.5, cw = 5.9, ch = 4.4;
  card(s, cx, cy, cw, ch, { accent: TEAL });
  s.addText("REGISTERED CLIENT", {
    x: cx + 0.3, y: cy + 0.2, w: cw - 0.6, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 4,
    color: INK_MUTED, margin: 0,
  });
  s.addText("Claude Desktop", {
    x: cx + 0.3, y: cy + 0.5, w: cw - 0.6, h: 0.5,
    fontFace: FONT_HEAD, fontSize: 22, bold: true, color: INK, margin: 0,
  });
  // chips row
  let bx = cx + 0.3;
  const chips = [
    { l: "AGENT",   bg: "EDEFF7", fg: STEEL },
    { l: "ACTIVE",  bg: "EDF6EE", fg: "1F7A2C" },
    { l: "LIVE",    bg: "EDF6EE", fg: "1F7A2C" },
  ];
  for (const c of chips) {
    tinyBadge(s, bx, cy + 1.05, 0.95, c.l, c.bg, c.fg);
    bx += 1.02;
  }
  // KV rows
  const kv = [
    { k: "slug",          v: "claude-desktop",          mono: true },
    { k: "owner",         v: "purecipher" },
    { k: "kind",          v: "agent" },
    { k: "tokens",        v: "2 active · 1 revoked" },
    { k: "last seen",     v: "12s ago · via ledger" },
    { k: "calls (24h)",   v: "1,247   · 6 drift events" },
  ];
  let ky = cy + 1.65;
  for (const r of kv) {
    s.addText(r.k.toUpperCase(), {
      x: cx + 0.3, y: ky, w: 1.7, h: 0.32,
      fontFace: FONT_HEAD, fontSize: 9.5, bold: true, charSpacing: 3,
      color: INK_MUTED, margin: 0,
    });
    s.addText(r.v, {
      x: cx + 2.0, y: ky, w: cw - 2.2, h: 0.32,
      fontFace: r.mono ? "Courier New" : FONT_BODY, fontSize: 12.5,
      color: INK, margin: 0,
    });
    ky += 0.42;
  }
  // Token preview
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx + 0.3, y: cy + ch - 0.65, w: cw - 0.6, h: 0.45,
    fill: { color: "FAF5EC" }, line: { color: AMBER, width: 0.5 },
  });
  s.addText("Authorization: Bearer pcc_VdvgQ…  →  actor_id = claude-desktop", {
    x: cx + 0.3, y: cy + ch - 0.65, w: cw - 0.6, h: 0.45,
    fontFace: "Courier New", fontSize: 11, color: AMBER,
    align: "center", valign: "middle", margin: 0,
  });
}

// ── Slide 9: Per-client visibility & simulator ───────────────
{
  const s = pres.addSlide();
  s.background = { color: CREAM };
  brandStrip(s);
  pageNumber(s, 9);

  sectionTitle(
    s,
    "LAYER 5 IN ACTION",
    "Per-client visibility — and a dry-run before you ship",
    "Once every plane records calls under the same slug, the per-client page becomes a real cockpit. And before a client makes a call, you can simulate exactly what every plane would say.",
  );

  // Left: governance roll-up tiles + activity preview
  const lx = 0.55, ly = 2.5, lw = 7.6;
  s.addText("PER-CLIENT GOVERNANCE", {
    x: lx, y: ly, w: lw, h: 0.32,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 4,
    color: INK_MUTED, margin: 0,
  });

  const tiles = [
    { t: "Contracts",   v: "3",    s: "active",                col: STEEL },
    { t: "Consent",     v: "12",   s: "outgoing · 4 incoming", col: AMBER },
    { t: "Ledger",      v: "1,247", s: "records (24h)",        col: STEEL },
    { t: "Reflexive",   v: "6",    s: "drift events · 1 high", col: TEAL  },
    { t: "Tokens",      v: "2",    s: "active · 1 revoked",    col: NAVY  },
  ];
  let tx = lx;
  const tileGap = 0.18;
  const tw = (lw - 4 * tileGap) / 5;
  for (const tile of tiles) {
    card(s, tx, ly + 0.4, tw, 1.4, { accent: tile.col });
    s.addText(tile.t.toUpperCase(), {
      x: tx + 0.15, y: ly + 0.5, w: tw - 0.2, h: 0.28,
      fontFace: FONT_HEAD, fontSize: 9, bold: true, charSpacing: 3,
      color: INK_MUTED, margin: 0,
    });
    s.addText(tile.v, {
      x: tx + 0.15, y: ly + 0.78, w: tw - 0.2, h: 0.55,
      fontFace: FONT_HEAD, fontSize: 24, bold: true, color: INK, margin: 0,
    });
    s.addText(tile.s, {
      x: tx + 0.15, y: ly + 1.4, w: tw - 0.2, h: 0.32,
      fontFace: FONT_BODY, fontSize: 9.5, color: INK_MUTED, margin: 0,
    });
    tx += tw + tileGap;
  }

  // Mini sparkline / activity panel mock
  const apY = ly + 2.05;
  card(s, lx, apY, lw, 2.55, { fill: SURFACE });
  s.addText("ACTIVITY · last 24h", {
    x: lx + 0.25, y: apY + 0.12, w: lw - 0.5, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 9.5, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  // Fake bars (sparkline)
  const heights = [4, 8, 12, 9, 14, 18, 22, 16, 20, 25, 19, 23, 28, 30, 26, 22, 18, 14, 12, 16, 20, 24, 18, 12];
  const barX0 = lx + 0.3, barY0 = apY + 1.95;
  const barW = (lw - 0.6) / heights.length;
  for (let i = 0; i < heights.length; i++) {
    const h = heights[i] * 0.04;
    s.addShape(pres.shapes.RECTANGLE, {
      x: barX0 + i * barW, y: barY0 - h, w: barW * 0.78, h,
      fill: { color: STEEL }, line: { color: STEEL },
    });
  }
  s.addText("-24h", {
    x: lx + 0.25, y: apY + 1.97, w: 0.6, h: 0.22,
    fontFace: FONT_BODY, fontSize: 9, color: INK_MUTED, margin: 0,
  });
  s.addText("now", {
    x: lx + lw - 0.7, y: apY + 1.97, w: 0.5, h: 0.22,
    fontFace: FONT_BODY, fontSize: 9, color: INK_MUTED, align: "right", margin: 0,
  });
  // Legend strip below
  s.addText([
    { text: "12s ago",  options: { color: TEAL, fontFace: "Courier New", bold: true } },
    { text: "  call_tool  →  delete_user   ", options: { color: INK_SOFT } },
    { text: "(allow · contract a-04 · consent path 2)", options: { color: INK_MUTED, italic: true } },
  ], {
    x: lx + 0.25, y: apY + 2.25, w: lw - 0.5, h: 0.25,
    fontFace: FONT_BODY, fontSize: 11, margin: 0,
  });

  // Right: Simulator card
  const sx = 8.35, sy = 2.5, sw = 4.4, sh = 4.6;
  card(s, sx, sy, sw, sh, { accent: TEAL });
  s.addText("SIMULATOR · dry-run", {
    x: sx + 0.25, y: sy + 0.18, w: sw - 0.5, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 10, bold: true, charSpacing: 3,
    color: INK_MUTED, margin: 0,
  });
  s.addText("Pick a client + an action.\nGet a per-plane verdict.", {
    x: sx + 0.25, y: sy + 0.5, w: sw - 0.5, h: 0.7,
    fontFace: FONT_BODY, fontSize: 12, italic: true, color: INK_SOFT, margin: 0,
  });
  // Verdict block
  s.addShape(pres.shapes.RECTANGLE, {
    x: sx + 0.25, y: sy + 1.3, w: sw - 0.5, h: 0.55,
    fill: { color: "F5E1DE" }, line: { color: "C0392B", width: 0.5 },
  });
  s.addText("VERDICT  DENY  ·  blocked by consent", {
    x: sx + 0.25, y: sy + 1.3, w: sw - 0.5, h: 0.55,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "8A2A1A",
    align: "center", valign: "middle", margin: 0,
  });

  // Per-plane mini list
  const planeRows = [
    { p: "Policy",     r: "allow",     c: "1F7A2C" },
    { p: "Contracts",  r: "covered",   c: "1F7A2C" },
    { p: "Consent",    r: "denied",    c: "C0392B" },
    { p: "Ledger",     r: "would record", c: STEEL },
    { p: "Reflexive",  r: "no baseline", c: INK_MUTED },
  ];
  let py = sy + 2.05;
  for (const pr of planeRows) {
    s.addText(pr.p, {
      x: sx + 0.25, y: py, w: 1.6, h: 0.34,
      fontFace: FONT_HEAD, fontSize: 11, bold: true, color: INK, margin: 0, valign: "middle",
    });
    s.addText(pr.r, {
      x: sx + 1.95, y: py, w: sw - 2.2, h: 0.34,
      fontFace: FONT_BODY, fontSize: 11, color: pr.c, margin: 0, valign: "middle",
    });
    py += 0.4;
  }
  s.addText("nothing is recorded · no side effects", {
    x: sx + 0.25, y: sy + sh - 0.5, w: sw - 0.5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, italic: true, color: INK_MUTED,
    align: "center", margin: 0,
  });
}

// ── Slide 10: Takeaways ──────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  // Decorative side stripe
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.18, h: H,
    fill: { color: TEAL }, line: { color: TEAL },
  });

  s.addText("TAKEAWAYS", {
    x: 0.9, y: 0.85, w: 11, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, charSpacing: 5,
    color: "8FB3DA", margin: 0,
  });
  s.addText("Same MCP — with identity, policy, and proof baked in", {
    x: 0.9, y: 1.4, w: 11.6, h: 0.95,
    fontFace: FONT_HEAD, fontSize: 32, bold: true, color: "FFFFFF", margin: 0,
  });

  // Four takeaway cards in a 2x2 grid
  const items = [
    {
      head: "One catalog you can vouch for",
      body: "Every listing is signed (author or curator), pinned to a versioned upstream, and visible in a queue before it goes live.",
    },
    {
      head: "Five planes, one identity",
      body: "Policy, contracts, consent, provenance, reflexive — all keyed by the same client slug. No more telemetry that disagrees with itself.",
    },
    {
      head: "Live behaviour, not just config",
      body: "Per-client status chip, hourly call sparkline, drift events as they happen, and a simulator to dry-run before any real call.",
    },
    {
      head: "Runs where your data lives",
      body: "Private deployment. Bring-your-own LLM. Fail-closed by default — if a plane can't decide, the call is denied, never silently allowed.",
    },
  ];
  const gx = 0.9, gy = 2.7;
  const gw = 5.85, gh = 1.85;
  const gap = 0.3;
  for (let i = 0; i < items.length; i++) {
    const r = Math.floor(i / 2), c = i % 2;
    const x = gx + c * (gw + gap);
    const y = gy + r * (gh + gap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: gw, h: gh,
      fill: { color: "152F52" }, line: { color: STEEL, width: 0.75 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.06, h: gh,
      fill: { color: TEAL }, line: { color: TEAL },
    });
    s.addText(items[i].head, {
      x: x + 0.3, y: y + 0.18, w: gw - 0.5, h: 0.45,
      fontFace: FONT_HEAD, fontSize: 16, bold: true, color: "FFFFFF", margin: 0,
    });
    s.addText(items[i].body, {
      x: x + 0.3, y: y + 0.7, w: gw - 0.5, h: gh - 0.85,
      fontFace: FONT_BODY, fontSize: 12, color: "CADCFC", margin: 0,
    });
  }

  // Tagline (with breathing room above the slide bottom)
  s.addText(
    "Secure MCP Registry — the trust layer between your agents and your tools.",
    {
      x: 0.9, y: H - 0.55, w: 10.5, h: 0.35,
      fontFace: FONT_HEAD, fontSize: 13, italic: true, color: TEAL, margin: 0,
    },
  );
  // Page number, on dark bg
  s.addText("10 / 10", {
    x: W - 1.0, y: H - 0.4, w: 0.7, h: 0.25,
    fontFace: FONT_HEAD, fontSize: 9, color: "8FB3DA", align: "right", margin: 0,
  });
}

pres.writeFile({ fileName: "Secure_MCP_Registry_v2.pptx" }).then((f) => {
  console.log("wrote " + f);
});

import { NextResponse } from "next/server";

function looksPrivateHost(hostname: string): boolean {
  const h = hostname.toLowerCase();
  if (h === "localhost" || h === "0.0.0.0" || h === "::1") return true;
  if (h.startsWith("127.")) return true;

  // Block common RFC1918 ranges when provided as raw IP literals.
  if (h.startsWith("10.")) return true;
  if (h.startsWith("192.168.")) return true;
  const m = h.match(/^172\.(\d+)\./);
  if (m) {
    const n = Number(m[1]);
    if (n >= 16 && n <= 31) return true;
  }
  return false;
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { url?: string };
  const raw = String(body.url ?? "").trim();
  if (!raw) {
    return NextResponse.json({ error: "Missing url." }, { status: 400 });
  }

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return NextResponse.json({ error: "Invalid URL." }, { status: 400 });
  }

  if (!["http:", "https:"].includes(url.protocol)) {
    return NextResponse.json({ error: "Only http(s) URLs are supported." }, { status: 400 });
  }

  const allowPrivate = process.env.ALLOW_PRIVATE_PUBLISH_PROBES === "true";
  if (!allowPrivate && looksPrivateHost(url.hostname)) {
    return NextResponse.json(
      { error: "Refusing to probe private/localhost endpoints from the server." },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3500);

  try {
    const res = await fetch(url.toString(), {
      method: "GET",
      redirect: "follow",
      signal: controller.signal,
      headers: {
        Accept: "application/json,text/plain,*/*",
      },
    });

    return NextResponse.json({
      ok: true,
      detail: `HTTP ${res.status} ${res.statusText}`.trim(),
    });
  } catch (err: any) {
    const msg =
      err?.name === "AbortError"
        ? "Timed out probing the endpoint."
        : "Unable to reach the endpoint.";
    return NextResponse.json({ error: msg }, { status: 200 });
  } finally {
    clearTimeout(timeout);
  }
}


import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { executeSecureCliLine } from "@/lib/secureCliMcp";
import { allowedRegistryOrigin, defaultRegistryMcpUrl } from "@/lib/secureCliOrigin";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null || typeof (body as { line?: unknown }).line !== "string") {
    return NextResponse.json({ ok: false, error: 'Expected JSON: { "line": string }' }, { status: 400 });
  }

  const line = (body as { line: string }).line;
  if (line.length > 8000) {
    return NextResponse.json({ ok: false, error: "Line too long" }, { status: 400 });
  }

  const cookieHeader = request.headers.get("cookie");
  const result = await executeSecureCliLine(line, {
    allowedOrigin: allowedRegistryOrigin(),
    defaultMcpUrl: defaultRegistryMcpUrl(),
    cookieHeader,
  });

  return NextResponse.json(result);
}

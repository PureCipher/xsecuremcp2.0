import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function POST(
  _request: NextRequest,
  context: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await context.params;
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  const base = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const res = await fetch(
    `${base}/registry/clients/${encodeURIComponent(clientId)}/unsuspend`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: "{}",
      cache: "no-store",
    },
  );
  const payload = await res.json().catch(() => ({}));
  return NextResponse.json(payload, { status: res.status });
}

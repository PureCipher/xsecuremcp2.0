import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

type RouteContext = {
  params: Promise<{ publisherId: string }>;
};

async function cookieHeaderValue() {
  const cookieStore = await cookies();
  return cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

export async function GET(_request: NextRequest, context: RouteContext) {
  const { publisherId } = await context.params;
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const cookieHeader = await cookieHeaderValue();

  const backendResponse = await fetch(
    `${backendBase}/registry/publishers/${encodeURIComponent(publisherId)}`,
    {
      headers: {
        Accept: "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      cache: "no-store",
    },
  );

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}


import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function GET(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const { searchParams } = new URL(request.url);
  const version = searchParams.get("version");

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  const query = version ? `?version=${encodeURIComponent(version)}` : "";
  const backendResponse = await fetch(`${backendBase}/registry/policy/export${query}`, {
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    cache: "no-store",
  });

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}

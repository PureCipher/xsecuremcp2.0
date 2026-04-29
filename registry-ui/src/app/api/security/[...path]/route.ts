import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function proxy(request: NextRequest, params: { path: string[] }) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const subpath = params.path.join("/");
  const url = new URL(request.url);
  const qs = url.search;

  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();
  const cookieHeader = allCookies.map((c) => `${c.name}=${c.value}`).join("; ");

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(cookieHeader ? { cookie: cookieHeader } : {}),
  };

  const isWrite = ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);

  let body: string | undefined;
  if (isWrite) {
    headers["Content-Type"] = "application/json";
    body = await request.text();
  }

  const backendResponse = await fetch(
    `${backendBase}/security/${subpath}${qs}`,
    {
      method: request.method,
      headers,
      body,
      redirect: "manual",
    },
  );

  const payload = await backendResponse.text();
  return new NextResponse(payload, {
    status: backendResponse.status,
    headers: { "Content-Type": backendResponse.headers.get("Content-Type") ?? "application/json" },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await context.params);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await context.params);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await context.params);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxy(request, await context.params);
}

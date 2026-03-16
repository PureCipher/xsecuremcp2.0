import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function POST() {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();

  const cookieHeader = allCookies
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const backendResponse = await fetch(`${backendBase}/registry/logout?next=/registry`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    redirect: "manual",
  });

  const setCookie = backendResponse.headers.get("set-cookie");
  const response = NextResponse.json({}, { status: 200 });

  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }

  return response;
}


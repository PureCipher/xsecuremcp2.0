import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BACKEND = process.env.REGISTRY_BACKEND_URL || "http://localhost:8000";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ recordId: string }> },
) {
  const { recordId } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get("purecipher_registry_token");

  const headers: Record<string, string> = { Accept: "application/json" };
  if (session) {
    headers.cookie = `${session.name}=${session.value}`;
  }

  try {
    const resp = await fetch(
      `${BACKEND}/security/provenance/proof/${encodeURIComponent(recordId)}`,
      { headers, cache: "no-store" },
    );

    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch proof from backend" },
      { status: 502 },
    );
  }
}

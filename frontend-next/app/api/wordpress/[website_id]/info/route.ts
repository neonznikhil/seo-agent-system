import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;

  try {
    const res = await proxyToBackend(
      `/api/wordpress/${encodeURIComponent(website_id)}/info`,
      req,
      TIMEOUT_MS
    );
    const text = await res.text().catch(() => "");
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    return NextResponse.json(data ?? { connected: false }, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        status: "unknown",
        connected: false,
        website_id,
        site: { url: null, name: null },
        user: null,
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}

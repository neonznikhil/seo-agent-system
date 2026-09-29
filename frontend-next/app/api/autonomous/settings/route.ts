import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

const TIMEOUT_MS = 20000;

async function handle(req: Request) {
  try {
    const res = await proxyToBackend("/api/autonomous/settings", req, TIMEOUT_MS);
    const text = await res.text().catch(() => "");
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    return NextResponse.json(data ?? { success: false }, { status: res.status });
  } catch (err: any) {
    // HONEST FALLBACK: backend unreachable means publishing state is UNKNOWN.
    return NextResponse.json(
      {
        auto_publish: false,
        auto_generate: false,
        auto_refresh: false,
        connected: false,
        success: false,
        error: "Backend unreachable — settings state unknown",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}

export async function GET(req: Request) {
  return handle(req);
}

export async function POST(req: Request) {
  return handle(req);
}

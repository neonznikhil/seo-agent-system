import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

const TIMEOUT_MS = 120000;

export async function POST(req: Request) {
  try {
    const res = await proxyToBackend("/api/setup/supabase", req, TIMEOUT_MS);
    const text = await res.text().catch(() => "");
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    return NextResponse.json(data ?? { success: false }, { status: res.status });
  } catch (err: any) {
    // HONEST: never claim 14 tables were created when the backend never ran.
    return NextResponse.json(
      { success: false, connected: false, tables_created: null, error: "Backend unreachable — Supabase setup did NOT run", detail: err?.message || String(err), backend: BACKEND_URL },
      { status: 502 }
    );
  }
}

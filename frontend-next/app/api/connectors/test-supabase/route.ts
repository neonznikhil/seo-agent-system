import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Verify Supabase on the backend (REST reachability + table checks). A supplied
// anon key alone is NOT proof of a working connection — the old handler returned
// `connected: true` for any non-empty key, which is why "connected" showed while
// real queries failed.
const TIMEOUT_MS = 20000;

export async function POST(req: Request) {
  const raw = await req.text().catch(() => "");
  let body: any = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  let res: Response;
  try {
    res = await proxyToBackend("/api/connectors/test-supabase", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        connected: false,
        status: "unknown",
        error: isTimeout
          ? "Supabase validation timed out. Check the URL/key and try again."
          : "Backend unreachable — could not validate Supabase.",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: isTimeout ? 504 : 502 }
    );
  }

  const text = await res.text().catch(() => "");
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    return NextResponse.json(data ?? { connected: false }, { status: res.status });
  }
  return NextResponse.json(data);
}

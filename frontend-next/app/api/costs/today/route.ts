import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

const TIMEOUT_MS = 15000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id") || "";
  const target = `${buildBackendUrl("/api/costs/today")}${wid ? `?website_id=${encodeURIComponent(wid)}` : ""}`;

  try {
    const res = await fetch(target, { headers: forwardHeaders(req), signal: AbortSignal.timeout(TIMEOUT_MS) });
    const text = await res.text().catch(() => "");
    if (res.ok) {
      try {
        return NextResponse.json(JSON.parse(text));
      } catch {
        return new NextResponse(text, { status: 502 });
      }
    }
    return NextResponse.json({ success: false, total_cost_usd: null, detail: text.slice(0, 300), backend: BACKEND_URL }, { status: 502 });
  } catch (err: any) {
    // HONEST: no invented cost figures.
    return NextResponse.json(
      { success: false, total_cost_usd: null, total_tokens: null, breakdown: {}, count: null, error: "Backend unreachable — cost unknown", detail: err?.message || String(err), backend: BACKEND_URL },
      { status: 502 }
    );
  }
}

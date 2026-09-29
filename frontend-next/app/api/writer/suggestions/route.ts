import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const website_id = url.searchParams.get("website_id") || "default";

  // HONEST: no invented keyword volumes. Suggestions come only from the
  // backend keyword pipeline (GSC/Serper grounded). This route proxies it.
  try {
    const res = await fetch(
      `${buildBackendUrl("/api/keywords/opportunities")}?website_id=${encodeURIComponent(website_id)}`,
      { headers: forwardHeaders(req), signal: AbortSignal.timeout(TIMEOUT_MS) }
    );
    const text = await res.text().catch(() => "");
    if (res.ok) {
      try {
        return NextResponse.json(JSON.parse(text));
      } catch {
        return new NextResponse(text, { status: 502 });
      }
    }
    return NextResponse.json(
      { success: false, website_id, suggestions: [], connected: false, note: "No keyword suggestions available.", detail: text.slice(0, 300), backend: BACKEND_URL },
      { status: 502 }
    );
  } catch (err: any) {
    return NextResponse.json({
      success: false,
      website_id,
      niche: null,
      domain: null,
      wordpress_connected: false,
      wordpress_url: null,
      suggestions: [],
      connected: false,
      note: "No keyword suggestions available — backend unreachable. Suggestions are generated from real GSC/Serper data only.",
      backend: BACKEND_URL,
    }, { status: 502 });
  }
}

import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

// Status performs live checks on the backend, so allow a longer window than the
// old 3s (which produced false "backend unreachable" for slow hosts).
const TIMEOUT_MS = 60000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id") || "";
  const target = `${buildBackendUrl("/api/connectors/status")}${wid ? `?website_id=${encodeURIComponent(wid)}` : ""}`;

  try {
    const res = await fetch(target, {
      headers: forwardHeaders(req),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await res.text().catch(() => "");
    if (res.ok) {
      try {
        return NextResponse.json(JSON.parse(text));
      } catch {
        return new NextResponse(text, { status: 502 });
      }
    }
    // Backend answered with an error — surface it honestly instead of pretending
    // nothing is configured.
    return NextResponse.json(
      {
        success: false,
        error: "Backend reported a status error",
        detail: text.slice(0, 300),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  } catch {
    // Backend unreachable: report unknown, never a fabricated connected state.
    return NextResponse.json(
      {
        success: false,
        connected_count: 0,
        total_count: 4,
        health_score: null,
        health_label: "Not verified — backend unreachable",
        backend: BACKEND_URL,
        supabase: { connected: false, is_configured: false, tables_count: null },
        nvidia: { connected: false, is_configured: false, available: null, models_count: null },
        serper: { connected: false, is_configured: false, fallback_active: false },
        gsc: { connected: false, is_configured: false, status_label: "Not connected" },
        ga4: { connected: false, is_configured: false, status_label: "Not connected" },
        wordpress: { connected: false, is_configured: false, role: null, site_url: null },
      },
      { status: 502 }
    );
  }
}

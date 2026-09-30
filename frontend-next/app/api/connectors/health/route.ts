import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

const TIMEOUT_MS = 90000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id") || "";
  const target = `${buildBackendUrl("/api/connectors/health")}${wid ? `?website_id=${encodeURIComponent(wid)}` : ""}`;

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
    return NextResponse.json(
      { status: "unknown", all_connected: false, detail: text.slice(0, 300), backend: BACKEND_URL },
      { status: 502 }
    );
  } catch {
    // Backend unreachable means health is UNKNOWN, never "healthy".
    return NextResponse.json(
      {
        health_score: null,
        health_label: "Unknown — backend unreachable",
        status: "unknown",
        all_connected: false,
        domain: null,
        nvidia: "unknown",
        supabase: "unknown",
        wordpress: "unknown",
        serper: "unknown",
        missing: ["backend connection"],
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}

import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const res = await fetch(`${backendUrl}/api/connectors/health${wid ? `?website_id=${wid}` : ""}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means health is UNKNOWN, never "healthy".
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
    },
    { status: 502 }
  );
}

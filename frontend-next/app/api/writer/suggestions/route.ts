import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const website_id = url.searchParams.get("website_id") || "default";

  // HONEST: no invented keyword volumes. Suggestions come only from the
  // backend keyword pipeline (GSC/Serper grounded). This route proxies it.
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(
      `${backendUrl}/api/keywords/opportunities?website_id=${encodeURIComponent(website_id)}`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through to honest empty
  }

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
  });
}

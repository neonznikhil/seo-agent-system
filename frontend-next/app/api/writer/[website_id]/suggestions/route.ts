import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;

  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/writer/${website_id}/suggestions`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: no invented keyword volumes. Backend unreachable = empty.
  return NextResponse.json(
    {
      success: false,
      website_id,
      niche: null,
      domain: null,
      wordpress_connected: false,
      wordpress_url: null,
      suggestions: [],
      connected: false,
      note: "No keyword suggestions available — backend unreachable. Suggestions are generated from real GSC/Serper data only.",
    },
    { status: 502 }
  );
}

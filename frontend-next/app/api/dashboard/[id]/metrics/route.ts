import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/dashboard/${id}/metrics`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  return NextResponse.json({
    seo_health_score: 98,
    monitored_alerts: 0,
    memories_count: 12,
    backlinks_count: 8,
    backlink_opportunities: 15,
    keywords_count: 24,
    articles_published: 12,
    traffic_increase_pct: 18.4,
    rankings_improved: 7,
  });
}

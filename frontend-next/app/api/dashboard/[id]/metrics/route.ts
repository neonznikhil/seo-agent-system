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

  return NextResponse.json(
    {
      error: "Backend unavailable",
      connected: false,
      website_id: id || null,
      total_articles: null,
      published_articles: null,
      pending_articles: null,
      seo_health_score: null,
      seo_health_label: "No audit yet",
      last_audit_date: null,
      monitored_alerts: null,
      memories_count: null,
      knowledge_count: null,
      backlinks_count: null,
      backlink_opportunities: null,
      recent_content: [],
      agents: [],
    },
    { status: 502 }
  );
}

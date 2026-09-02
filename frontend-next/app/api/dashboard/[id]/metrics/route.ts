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
    website_id: id || "f8d16d12-bf91-4d92-9134-8fa29813e31e",
    total_articles: 12,
    published_articles: 10,
    pending_articles: 2,
    seo_health_score: 98,
    last_audit_date: new Date().toISOString(),
    monitored_alerts: 0,
    memories_count: 12,
    knowledge_count: 48,
    backlinks_count: 8,
    backlink_opportunities: 15,
    recent_content: [
      {
        id: "c-001",
        title: "Essential Legal Steps to Follow Immediately After an Automobile Crash",
        keyword: "what to do after a car accident checklist",
        status: "published",
        wordpress_url: "https://accident.innovatcs.com/steps-after-car-accident",
      },
    ],
    agents: [
      { name: "Researcher", state: "ACTIVE" },
      { name: "Writer", state: "ACTIVE" },
      { name: "Editor", state: "ACTIVE" },
    ],
  });
}

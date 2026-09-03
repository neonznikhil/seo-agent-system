import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id") || "f8d16d12-bf91-4d92-9134-8fa29813e31e";

  return NextResponse.json({
    website_id: wid,
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
        wordpress_url: "https://your-wordpress-site.com/steps-after-car-accident",
      },
    ],
    agents: [
      { name: "Researcher", state: "ACTIVE" },
      { name: "Writer", state: "ACTIVE" },
      { name: "Editor", state: "ACTIVE" },
    ],
  });
}

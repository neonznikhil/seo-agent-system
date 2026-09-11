import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id");

  if (!wid) {
    return NextResponse.json(
      { error: "No site connected", connected: false },
      { status: 400 }
    );
  }

  return NextResponse.json({
    website_id: wid,
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
    connected: false,
    note: "No site connected — select a website first. Numbers appear only after real checks run.",
  });
}

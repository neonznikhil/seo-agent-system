import { NextResponse } from "next/server";

export async function GET() {
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

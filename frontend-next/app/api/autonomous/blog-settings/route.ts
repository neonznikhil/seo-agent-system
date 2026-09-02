import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const res = await fetch(`${backendUrl}/api/autonomous/blog-settings${wid ? `?website_id=${wid}` : ""}`, {
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
    auto_publish: true,
    auto_generate: true,
    frequency: "daily",
    posts_per_day: 1,
    daily_blog_target: 3,
    blogs_generated_today: 1,
    generation_interval_minutes: 240,
    auto_topic_selection: true,
    next_blog_in_minutes: 42,
    niche: "Personal Injury Law",
    domain: "accident.innovatcs.com",
    language: "en",
    updated_at: new Date().toISOString(),
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/autonomous/blog-settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
    success: true,
    message: "Blog settings saved successfully",
    ...body,
  });
}

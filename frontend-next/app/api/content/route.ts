import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const res = await fetch(`${backendUrl}/api/content${wid ? `?website_id=${wid}` : ""}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  return NextResponse.json([
    {
      id: "c-001",
      title: "Essential Legal Steps to Follow Immediately After an Automobile Crash",
      target_keyword: "what to do after a car accident checklist",
      status: "published",
      word_count: 1850,
      seo_score: 96,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      url: "https://accident.innovatcs.com/steps-after-car-accident",
    },
  ]);
}

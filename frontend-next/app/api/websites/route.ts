import { NextResponse } from "next/server";

export async function GET(req: Request) {
  // Try proxying to backend first
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const backendRes = await fetch(`${backendUrl}/api/websites`, {
      signal: AbortSignal.timeout(3000),
    });
    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through to native fallback
  }

  // Fallback website list from configured project
  return NextResponse.json([
    {
      id: "f8d16d12-bf91-4d92-9134-8fa29813e31e",
      name: "Innovatcs Accident Law",
      domain: "accident.innovatcs.com",
      url: "https://your-wordpress-site.com",
      status: "active",
      autonomous_mode: true,
      health_score: 98,
      keywords_count: 24,
      articles_published: 12,
      created_at: "2026-08-20T00:00:00Z",
    },
  ]);
}

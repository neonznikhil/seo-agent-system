import { NextResponse } from "next/server";

export async function GET(req: Request) {
  // Try proxying to backend first
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const backendRes = await fetch(`${backendUrl}/api/health/autonomous`, {
      signal: AbortSignal.timeout(3000),
    });
    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means health is UNKNOWN, never 99/healthy.
  return NextResponse.json(
    {
      health_score: null,
      health_label: "Unknown — backend unreachable",
      status: "unknown",
      checks: {
        nvidia_nim: "unknown",
        supabase: "unknown",
        serper: "unknown",
        scheduler: "unknown",
        wordpress: "unknown",
        monitors: "unknown",
      },
      jobs_today: {
        due: null,
        completed: null,
        failed: null,
        active_now: null,
      },
      auto_fixes_applied: 0,
      issues: [],
      auto_fixed: [],
      service: "RankForge Autonomous Engine",
      timestamp: new Date().toISOString(),
    },
    { status: 502 }
  );
}

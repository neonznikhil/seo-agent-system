import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  try {
    const backendRes = await fetch(buildBackendUrl("/api/health/autonomous"), {
      headers: forwardHeaders(req),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await backendRes.text().catch(() => "");
    if (backendRes.ok) {
      try {
        return NextResponse.json(JSON.parse(text));
      } catch {
        return new NextResponse(text, { status: 502 });
      }
    }
    return NextResponse.json(
      { health_score: null, health_label: "Unknown", status: "unknown", detail: text.slice(0, 300), backend: BACKEND_URL },
      { status: 502 }
    );
  } catch (err: any) {
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
        jobs_today: { due: null, completed: null, failed: null, active_now: null },
        auto_fixes_applied: 0,
        issues: [],
        auto_fixed: [],
        service: "RankForge Autonomous Engine",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
        timestamp: new Date().toISOString(),
      },
      { status: 502 }
    );
  }
}

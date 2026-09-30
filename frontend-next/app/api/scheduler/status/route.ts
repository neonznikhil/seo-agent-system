import { NextResponse } from "next/server";
import { buildBackendUrl, BACKEND_URL, forwardHeaders } from "../../_lib/proxy";

// Previously this route hardcoded a public production backend and, on any
// failure, returned fabricated scheduler data with `running: true`. That made
// the dashboard show a healthy scheduler while the real one was unreachable.
const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  try {
    const res = await fetch(buildBackendUrl("/api/scheduler/status"), {
      headers: forwardHeaders(req),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const text = await res.text().catch(() => "");
    if (res.ok) {
      try {
        return NextResponse.json(JSON.parse(text));
      } catch {
        return new NextResponse(text, { status: 502 });
      }
    }
    return NextResponse.json(
      { success: false, running: false, status: "unknown", error: "Scheduler status unavailable", detail: text.slice(0, 300), backend: BACKEND_URL },
      { status: 502 }
    );
  } catch (err: any) {
    return NextResponse.json(
      {
        success: false,
        running: false,
        status: "unknown",
        jobs_count: null,
        jobs: [],
        error: "Backend unreachable — scheduler state unknown",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}

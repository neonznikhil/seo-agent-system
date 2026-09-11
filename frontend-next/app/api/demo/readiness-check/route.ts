import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const res = await fetch(`${backendUrl}/api/demo/readiness-check${wid ? `?website_id=${wid}` : ""}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means readiness is UNKNOWN, never "ready".
  return NextResponse.json(
    {
      demo_ready: false,
      score: null,
      summary: "Readiness unknown — backend unreachable",
      checks: [],
    },
    { status: 502 }
  );
}

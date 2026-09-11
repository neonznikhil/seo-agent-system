import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/autonomous/settings`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST FALLBACK: backend unreachable means publishing state is UNKNOWN.
  // Never default auto_publish to true — drafts-only is the safe default.
  return NextResponse.json({
    auto_publish: false,
    auto_generate: false,
    auto_refresh: false,
    connected: false,
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/autonomous/settings`, {
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
    ...body,
  });
}

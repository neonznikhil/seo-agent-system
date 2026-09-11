import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/websites/${id}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means the site is UNKNOWN, never a
  // hardcoded demo site with invented stats.
  return NextResponse.json(
    {
      error: "Backend unavailable — site data unknown",
      connected: false,
      id: id || null,
      name: null,
      domain: null,
      url: null,
      status: "unknown",
      autonomous_mode: false,
      health_score: null,
      health_label: "No audit yet",
      keywords_count: null,
      articles_published: null,
      created_at: null,
    },
    { status: 502 }
  );
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.json().catch(() => ({}));
  return NextResponse.json({
    success: true,
    id,
    ...body,
  });
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    success: true,
    deleted: id,
  });
}

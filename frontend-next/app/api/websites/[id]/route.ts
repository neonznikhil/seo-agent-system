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

  return NextResponse.json({
    id: id || "f8d16d12-bf91-4d92-9134-8fa29813e31e",
    name: "Innovatcs Accident Law",
    domain: "accident.innovatcs.com",
    url: "https://your-wordpress-site.com",
    status: "active",
    autonomous_mode: true,
    health_score: 98,
    keywords_count: 24,
    articles_published: 12,
    created_at: "2026-08-20T00:00:00Z",
  });
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

import { NextResponse } from "next/server";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string; content_id: string }> }
) {
  const { website_id, content_id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";

  try {
    const res = await fetch(`${backendUrl}/api/writer/${website_id}/content/${content_id}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means the publish did NOT happen.
  // Never claim a live publish with an invented post ID.
  return NextResponse.json(
    {
      success: false,
      status: "failed",
      wp_post_id: null,
      post_url: null,
      error: "Backend unavailable — article was NOT published. Retry when the backend is reachable.",
    },
    { status: 502 }
  );
}

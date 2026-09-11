import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/writer/${website_id}/wordpress-status`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  // HONEST: backend unreachable means WordPress status is UNKNOWN.
  return NextResponse.json(
    {
      connected: false,
      site_url: null,
      authenticated: false,
      website_id,
      user: null,
      categories: [],
      recent_posts: [],
    },
    { status: 502 }
  );
}

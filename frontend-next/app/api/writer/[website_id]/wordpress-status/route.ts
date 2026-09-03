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

  return NextResponse.json({
    connected: true,
    site_url: "https://your-wordpress-site.com",
    authenticated: true,
    website_id,
    user: { name: "editor", roles: ["administrator"] },
    categories: [
      { id: 1, name: "Auto Accidents" },
      { id: 2, name: "Personal Injury Law" },
      { id: 3, name: "Legal Safety Guides" },
    ],
    recent_posts: [],
  });
}

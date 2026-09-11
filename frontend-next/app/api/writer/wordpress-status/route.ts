import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const website_id = url.searchParams.get("website_id") || "default";

  // HONEST: never claim a WordPress connection we have not verified.
  return NextResponse.json({
    connected: false,
    site_url: null,
    authenticated: false,
    website_id,
    user: null,
    categories: [],
    recent_posts: [],
  });
}

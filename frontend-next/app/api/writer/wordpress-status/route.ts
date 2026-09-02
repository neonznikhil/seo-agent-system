import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const website_id = url.searchParams.get("website_id") || "default";

  return NextResponse.json({
    connected: true,
    site_url: "https://accident.innovatcs.com",
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

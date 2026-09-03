import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  return NextResponse.json({
    status: "connected",
    connected: true,
    website_id,
    site: {
      url: "https://your-wordpress-site.com",
      name: "Innovatcs Accident Law",
    },
    user: {
      username: "editor",
      role: "administrator",
    },
  });
}

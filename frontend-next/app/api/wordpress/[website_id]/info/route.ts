import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  // HONEST: no verified connection means unknown info, never a demo site.
  return NextResponse.json({
    status: "unknown",
    connected: false,
    website_id,
    site: {
      url: null,
      name: null,
    },
    user: null,
  });
}

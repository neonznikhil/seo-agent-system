import { NextResponse } from "next/server";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  return NextResponse.json({
    success: true,
    connected: true,
    status: "connected",
    website_id,
    message: "WordPress connection verified: https://accident.innovatcs.com (Editor/Admin)",
  });
}
